import redis

# https://github.com/aio-libs/aioredis-py
from redis import asyncio as aioredis

KEY_OPENAI_API_KEY = 'openai_api_key'  # string.

# Default host and port.
rds = redis.from_url('redis://localhost:6379')
ards = aioredis.from_url('redis://localhost:6379')
