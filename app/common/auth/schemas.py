"""Auth schemas."""

from pydantic import BaseModel, EmailStr
from typing import Optional


class AdminUser(BaseModel):
    """Admin user info extracted from JWT token."""
    email: str
    username: Optional[str] = None
    role: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None

