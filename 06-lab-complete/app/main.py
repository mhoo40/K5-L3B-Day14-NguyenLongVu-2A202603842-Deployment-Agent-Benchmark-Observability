"""
Production AI Agent — Part 6 Final Project (bản khung)

Hoàn thành các TODO để đạt đủ 12 tiêu chí trong README.md, rồi kiểm tra:
    python check_production_ready.py

Bản khung này chạy được (uvicorn app.main:app) nhưng chưa đạt tiêu chí nào.
"""
import json
import logging
import json
import logging
import signal
import sys
import time
from contextlib import asynccontextmanager
from datetime import datetime, UTC

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.auth import verify_api_key
from app.config import settings
from app.cost_guard import check_budget, record_cost
from app.rate_limiter import check_rate_limit
from app.redis_client import r, redis_healthy
from utils.mock_llm import ask as llm_ask

# TODO (tiêu chí 10 — Structured logging):
#   Mỗi dòng log của app phải là 1 JSON object hợp lệ, vd
#   {"ts": "...", "lvl": "INFO", "event": "request", "path": "/ask", "status": 200, "ms": 12.3}
#   Gợi ý: tự viết logging.Formatter dùng json.dumps.
class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_record = {
            "ts": datetime.now(UTC).isoformat(),
            "lvl": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if hasattr(record, "extra_data") and isinstance(record.extra_data, dict):
            log_record.update(record.extra_data)
        return json.dumps(log_record, ensure_ascii=False)


handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(JsonFormatter())
logging.basicConfig(level=logging.INFO, handlers=[handler], force=True)
logger = logging.getLogger("production_agent")

is_shutting_down = False


# TODO (tiêu chí 11 — Graceful shutdown):
#   Khi nhận SIGTERM: ngừng nhận request mới, xử lý xong request đang chạy rồi thoát (exit code 0).
#   Gợi ý: dùng lifespan của FastAPI để dọn dẹp. Nếu tự đăng ký signal handler cho SIGTERM thì
#   phải gọi lại handler cũ của uvicorn, nếu không process sẽ không bao giờ tắt.
@asynccontextmanager
async def lifespan(app: FastAPI):
    global is_shutting_down
    prev_sigterm = signal.getsignal(signal.SIGTERM)

    def handle_sigterm(signum, frame):
        global is_shutting_down
        is_shutting_down = True
        logger.info("Received SIGTERM, shutting down gracefully")
        if callable(prev_sigterm):
            prev_sigterm(signum, frame)

    signal.signal(signal.SIGTERM, handle_sigterm)
    logger.info("Application started")
    yield
    is_shutting_down = True
    try:
        r.close()
    except Exception:
        pass
    logger.info("Application shutdown complete")


app = FastAPI(title="Production AI Agent", lifespan=lifespan)


@app.middleware("http")
async def request_logger(request: Request, call_next):
    if is_shutting_down and request.url.path != "/health":
        return JSONResponse(status_code=503, content={"detail": "Server is shutting down"})

    start = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = round((time.perf_counter() - start) * 1000, 2)

    logger.info(
        "request",
        extra={
            "extra_data": {
                "event": "request",
                "path": request.url.path,
                "status": response.status_code,
                "ms": elapsed_ms,
            }
        },
    )
    return response

class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)


# TODO (tiêu chí 4): GET /health — liveness: luôn trả 200 khi process còn chạy
#                    (kể cả khi Redis chưa kết nối được)
@app.get("/health")
def health():
    return {"status": "ok"}


# TODO (tiêu chí 5): GET /ready  — readiness: 200 khi sẵn sàng, 503 khi Redis không kết nối được
@app.get("/ready")
def ready():
    if is_shutting_down or not redis_healthy():
        return JSONResponse(status_code=503, content={"status": "not ready"})
    return {"status": "ready"}
    

@app.post("/ask")
def ask(
    body: AskRequest,
    api_key: str = Depends(verify_api_key),
):
    check_rate_limit(api_key)
    check_budget()

    answer = llm_ask(body.question)

    input_tokens = max(1, len(body.question) // 4)
    output_tokens = max(1, len(str(answer)) // 4)
    record_cost(input_tokens, output_tokens)

    return {"question": body.question, "answer": answer}
