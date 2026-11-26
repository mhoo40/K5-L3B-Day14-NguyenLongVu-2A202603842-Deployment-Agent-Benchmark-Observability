"""
Cost guard (tiêu chí 8).

Yêu cầu:
  • Cộng dồn chi phí LLM (tính theo token) vào Redis
  • Tổng chi phí vượt DAILY_BUDGET_USD (hoặc MONTHLY_BUDGET_USD) → HTTP 402
"""
"""
Cost guard (tiêu chí 8).
"""
from datetime import datetime, timezone
import redis
from fastapi import HTTPException
from app.config import settings
from app.redis_client import r

# Giá USD / 1K tokens (tham khảo gpt-4o-mini)
PRICE_INPUT_PER_1K = 0.00015
PRICE_OUTPUT_PER_1K = 0.0006


def _daily_budget_key() -> str:
    day_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return f"budget:daily:{day_str}"


def check_budget() -> None:
    """Gọi TRƯỚC khi gọi LLM. Hết budget → raise HTTPException(status_code=402)."""
    key = _daily_budget_key()
    try:
        spent = float(r.get(key) or 0.0)
        if spent >= settings.daily_budget_usd:
            raise HTTPException(
                status_code=402,
                detail="Daily budget exceeded.",
            )
    except HTTPException:
        raise
    except redis.RedisError:
        pass


def record_cost(input_tokens: int, output_tokens: int) -> float:
    """Gọi SAU khi gọi LLM. Cộng chi phí của request vào tổng, trả về chi phí request."""
    cost = (input_tokens / 1000.0) * PRICE_INPUT_PER_1K + (output_tokens / 1000.0) * PRICE_OUTPUT_PER_1K
    key = _daily_budget_key()
    try:
        r.incrbyfloat(key, cost)
        r.expire(key, 48 * 3600)
    except redis.RedisError:
        pass
    return cost

