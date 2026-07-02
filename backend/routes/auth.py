from fastapi import APIRouter, HTTPException, Depends
from database import get_db
from dependencies.services import get_user_service
from services.user_service import UserService
from schemas import UserCreate, UserLogin, TokenResponse
from services.security import verify_password, get_password_hash, create_access_token
from config import settings
from datetime import datetime, timedelta

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/signup", response_model=TokenResponse)
async def signup(user: UserCreate, user_service: UserService = Depends(get_user_service)):
    existing_user = await user_service.repo.find_one({"email": user.email})
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    hashed_password = get_password_hash(user.password)
    user_dict = {
        "name": user.name,
        "email": user.email,
        "hashed_password": hashed_password,
        "role": "Platform Administrator" if user.isAdmin else "Regional Survey Lead",
        "organization": user.organization,
        "isAdmin": user.isAdmin,
        "created_at": datetime.utcnow()
    }
    
    await user_service.repo.create(user_dict)
    
    access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
    access_token = create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    
    return {
        "access_token": access_token, 
        "token_type": "bearer",
        "user": {
            "name": user.name,
            "email": user.email,
            "role": user_dict["role"],
            "organization": user.organization,
            "isAdmin": user.isAdmin
        }
    }

@router.post("/login", response_model=TokenResponse)
async def login(user: UserLogin, user_service: UserService = Depends(get_user_service)):
    db_user = await user_service.repo.find_one({"email": user.email})
    if not db_user:
        raise HTTPException(status_code=400, detail="Incorrect email or password")
        
    if not verify_password(user.password, db_user["hashed_password"]):
        raise HTTPException(status_code=400, detail="Incorrect email or password")
        
    access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
    access_token = create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    
    return {
        "access_token": access_token, 
        "token_type": "bearer",
        "user": {
            "name": db_user.get("name"),
            "email": db_user.get("email"),
            "role": db_user.get("role"),
            "organization": db_user.get("organization"),
            "isAdmin": db_user.get("isAdmin", False)
        }
    }

@router.get("/users")
async def get_users(user_service: UserService = Depends(get_user_service)):
    users = await user_service.repo.find_many({})
    if not users:
        return [
            {"id": "u1", "name": "System Admin", "email": "admin@maritime.com", "role": "Platform Administrator", "status": "Active"},
            {"id": "u2", "name": "John Inspector", "email": "john@maritime.com", "role": "Regional Survey Lead", "status": "Active"}
        ]
    return [{"id": str(u["_id"]), "name": u.get("name"), "email": u.get("email"), "role": u.get("role", "Regional Survey Lead"), "status": "Active"} for u in users]

@router.post("/users/{email}/role")
async def update_role(email: str, payload: dict, user_service: UserService = Depends(get_user_service)):
    new_role = payload.get("role")
    if not new_role:
        raise HTTPException(status_code=400, detail="Role is required")
    await user_service.repo.update({"email": email}, {"role": new_role})
    return {"status": "success", "message": f"User {email} role updated to {new_role}"}

@router.post("/users/{email}/password")
async def update_password(email: str, payload: dict, user_service: UserService = Depends(get_user_service)):
    new_password = payload.get("password")
    if not new_password:
        raise HTTPException(status_code=400, detail="Password is required")
    
    hashed_password = get_password_hash(new_password)
    modified_count = await user_service.repo.update({"email": email}, {"hashed_password": hashed_password})
    if modified_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
        
    return {"status": "success", "message": f"Password updated successfully for {email}"}
