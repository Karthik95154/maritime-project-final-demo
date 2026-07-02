import time
import uuid
from fastapi import Request
from loguru import logger

async def request_id_middleware(request: Request, call_next):
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response

async def logging_middleware(request: Request, call_next):
    start_time = time.time()
    request_id = getattr(request.state, "request_id", "unknown")
    logger.info(f"[{request_id}] Started {request.method} {request.url.path}")
    
    response = await call_next(request)
    
    process_time = time.time() - start_time
    logger.info(f"[{request_id}] Completed {response.status_code} in {process_time:.3f}s")
    
    return response
