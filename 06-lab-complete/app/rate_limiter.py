"""
Rate limiting (tiêu chí 7).

Yêu cầu:
  • Mỗi API key tối đa RATE_LIMIT_PER_MINUTE request trong 60 giây (sliding window)
  • Vượt giới hạn → HTTP 429, nên kèm header Retry-After
  • State lưu trong Redis để mọi worker / instance dùng chung và vẫn còn sau khi
    restart agent (script chấm sẽ restart agent để kiểm tra)
"""
import time
import uuid
import redis
from fastapi import HTTPException
from app.config import settings
from app.redis_client import r


def check_rate_limit(key: str) -> None:
  # TODO: gợi ý dùng Redis sorted set: ZREMRANGEBYSCORE → ZCARD → ZADD → EXPIRE
    limit = settings.rate_limit_per_minute
    window = 60
    now = time.time()
    redis_key = f"ratelimit:{key}"

    try:
        pipe = r.pipeline()
        pipe.zremrangebyscore(redis_key, 0, now - window)
        pipe.zcard(redis_key)
        pipe.zadd(redis_key, {f"{now}:{uuid.uuid4().hex}": now})
        pipe.expire(redis_key, window + 5)
        _, current_count, _, _ = pipe.execute()

        if current_count >= limit:
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded ({limit} requests/minute).",
                headers={"Retry-After": str(window)},
            )
    except HTTPException:
        raise
    except redis.RedisError:
        pass
