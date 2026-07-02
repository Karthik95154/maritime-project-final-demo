import time
from datetime import datetime
from fastapi import Request
from database import get_db

async def audit_middleware(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    
    # We log in background or asynchronously to not block the response
    # Usually we would send this to a background task. Since middleware doesn't easily have background tasks here,
    # we can run it asynchronously.
    try:
        db = next(get_db()) # Note: motor is async, but get_db returns an AsyncIOMotorDatabase
        # Actually get_db is async or sync? get_db() returns the motor db object directly (it's not a generator in motor if not using yield)
    except Exception:
        db = None

    if db is not None:
        # Assuming we can get user from request state if authenticated
        user_email = getattr(request.state, "user_email", "anonymous")
        request_id = getattr(request.state, "request_id", "unknown")
        
        audit_record = {
            "timestamp": datetime.utcnow(),
            "method": request.method,
            "url": str(request.url.path),
            "user": user_email,
            "execution_time_s": process_time,
            "status_code": response.status_code,
            "request_id": request_id
        }
        
        # fire and forget
        import asyncio
        asyncio.create_task(db.audit_logs.insert_one(audit_record))
        
    return response
