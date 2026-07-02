from typing import Any, Optional
from pydantic import BaseModel

class APIResponse(BaseModel):
    success: bool
    message: str = ""
    data: Optional[Any] = None

class APIErrorDetail(BaseModel):
    code: str
    message: str

class APIErrorResponse(BaseModel):
    success: bool = False
    error: APIErrorDetail

def success_response(data: Any = None, message: str = "") -> dict:
    return {"success": True, "message": message, "data": data}

def error_response(code: str, message: str) -> dict:
    return {"success": False, "error": {"code": code, "message": message}}
