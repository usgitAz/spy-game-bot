"""Lua scripts executed atomically inside Redis.

Each script runs as a single, uninterruptible unit on the Redis server,
which is what actually prevents race conditions — two players clicking
'Join' at the exact same millisecond, or two admins racing to create a
game in the same group. Plain Python check-then-write (even with pipelines)
can't guarantee this because another client's command could run between
the check and the write; a Lua script can't be interleaved with anything.
"""

# KEYS[1] = meta key, KEYS[2] = players key, KEYS[3] = order key
# ARGV[1] = meta hash fields as a flat list (field1 value1 field2 value2 ...)
# ARGV[2] = creator_user_id (string)
# ARGV[3] = creator PlayerState JSON payload (pre-built in Python, is_creator=true)
# ARGV[4] = ttl_seconds (last argument)
# Returns: 1 if this call created the game, 0 if a game already existed.
CREATE_GAME = """
if redis.call('EXISTS', KEYS[1]) == 1 then
    return 0
end
local ttl = table.remove(ARGV)
local creator_json = table.remove(ARGV)
local creator_id = table.remove(ARGV)
redis.call('HSET', KEYS[1], unpack(ARGV))
redis.call('HSET', KEYS[2], creator_id, creator_json)
redis.call('RPUSH', KEYS[3], creator_id)
redis.call('EXPIRE', KEYS[1], ttl)
redis.call('EXPIRE', KEYS[2], ttl)
redis.call('EXPIRE', KEYS[3], ttl)
return 1
"""

# KEYS[1] = meta key, KEYS[2] = players key, KEYS[3] = order key
# ARGV[1] = user_id (string)
# ARGV[2] = player JSON payload (pre-built in Python)
# ARGV[3] = max_players
# ARGV[4] = ttl_seconds (re-applied so activity keeps the game alive)
# Returns: 1 = joined, -1 = game not in lobby, -2 = already joined, -3 = lobby full
JOIN_GAME = """
local status = redis.call('HGET', KEYS[1], 'status')
if not status or status ~= 'lobby' then
    return -1
end
if redis.call('HEXISTS', KEYS[2], ARGV[1]) == 1 then
    return -2
end
local count = redis.call('HLEN', KEYS[2])
if count >= tonumber(ARGV[3]) then
    return -3
end
redis.call('HSET', KEYS[2], ARGV[1], ARGV[2])
redis.call('RPUSH', KEYS[3], ARGV[1])
redis.call('EXPIRE', KEYS[1], ARGV[4])
redis.call('EXPIRE', KEYS[2], ARGV[4])
redis.call('EXPIRE', KEYS[3], ARGV[4])
return 1
"""

# KEYS[1] = meta key, KEYS[2] = players key, KEYS[3] = order key
# ARGV[1] = user_id (string)
# Returns: 1 = removed, -1 = game not in lobby, -2 = not a participant,
#          -3 = is the creator (creator cannot leave, must delete instead)
LEAVE_GAME = """
local status = redis.call('HGET', KEYS[1], 'status')
if not status or status ~= 'lobby' then
    return -1
end
local raw = redis.call('HGET', KEYS[2], ARGV[1])
if not raw then
    return -2
end
local player = cjson.decode(raw)
if player.is_creator then
    return -3
end
redis.call('HDEL', KEYS[2], ARGV[1])
redis.call('LREM', KEYS[3], 0, ARGV[1])
return 1
"""

# KEYS[1] = meta key, KEYS[2..4] = players/order/votes keys to drop together
# ARGV[1] = requester_user_id, ARGV[2] = requester_is_group_admin ("1"/"0")
# Returns: 1 = deleted, -1 = no active game, -2 = not authorized
DELETE_GAME = """
if redis.call('EXISTS', KEYS[1]) == 0 then
    return -1
end
local creator_id = redis.call('HGET', KEYS[1], 'creator_id')
if creator_id ~= ARGV[1] and ARGV[2] ~= '1' then
    return -2
end
redis.call('DEL', KEYS[1], KEYS[2], KEYS[3], KEYS[4])
return 1
"""

# KEYS[1] = meta key, KEYS[2] = votes key
# ARGV[1] = voter_id, ARGV[2] = target_id
# Returns: 1 = vote recorded, -1 = not in voting phase, -2 = already voted
RECORD_VOTE = """
local status = redis.call('HGET', KEYS[1], 'status')
if not status or status ~= 'voting' then
    return -1
end
if redis.call('HEXISTS', KEYS[2], ARGV[1]) == 1 then
    return -2
end
redis.call('HSET', KEYS[2], ARGV[1], ARGV[2])
return 1
"""
