from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class UserBase(BaseModel):
    """
    用户基础Schema
    """
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=100)
    full_name: Optional[str] = None


class UserCreate(UserBase):
    """
    用户创建Schema
    """
    password: str = Field(..., min_length=6, max_length=100)


class UserUpdate(BaseModel):
    """
    用户更新Schema
    """
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    password: Optional[str] = Field(None, min_length=6, max_length=100)


class UserResponse(UserBase):
    """
    用户响应Schema
    """
    id: int
    is_active: bool
    is_superuser: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class Token(BaseModel):
    """
    令牌Schema
    """
    access_token: str
    token_type: str


class TokenPayload(BaseModel):
    """
    令牌负载Schema
    """
    sub: Optional[int] = None
