from fastapi import Request
from fastapi.responses import JSONResponse
from loguru import logger
from utils.response import error_response

async def global_exception_middleware(request: Request, call_next):
    try:
        return await call_next(request)
    except Exception as exc:
        request_id = getattr(request.state, "request_id", "unknown")
        logger.error(f"[{request_id}] Unhandled exception: {str(exc)}")
        logger.exception(exc)
        return JSONResponse(
            status_code=500,
            content=error_response("INTERNAL_ERROR", "An unexpected internal server error occurred.")
        )
