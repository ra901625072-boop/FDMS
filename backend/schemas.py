from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional, List
from datetime import datetime

# ==========================================
# Authentication & User Schemas
# ==========================================

class UserRegister(BaseModel):
    username: str = Field(..., min_length=3, max_length=20, pattern=r"^[a-zA-Z0-9_]+$")
    email: EmailStr
    password: str = Field(..., min_length=8)
    
    @field_validator('password')
    def validate_password(cls, v):
        if not any(char.isupper() for char in v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not any(char.isdigit() for char in v):
            raise ValueError('Password must contain at least one number')
        return v

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    role: str
    created_at: datetime

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None
    user_id: Optional[int] = None
    role: Optional[str] = None

# ==========================================
# Family Schemas
# ==========================================

class FamilySetup(BaseModel):
    name: str = Field(..., min_length=2, max_length=40)
    max_members: int = Field(..., ge=2, le=20)

class FamilySetupResponse(BaseModel):
    family_id: str
    name: str
    secret_code: str # Plaintext, displayed only once
    max_members: int

class FamilyLogin(BaseModel):
    username: str
    email: EmailStr
    secret_code: str = Field(..., min_length=9, max_length=9) # e.g. "XXXX-XXXX"

class FamilyResponse(BaseModel):
    id: str
    name: str
    admin_id: int
    max_members: int
    created_at: datetime
    expires_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class FamilyMemberResponse(BaseModel):
    id: int
    family_id: str
    user_id: int
    role: str
    joined_at: datetime

    class Config:
        from_attributes = True

# ==========================================
# Storage Configuration Schemas (Legacy/Existing)
# ==========================================

class StorageSetupMega(BaseModel):
    email: str
    password: str

class StorageConfigResponse(BaseModel):
    storage_provider: Optional[str] = None
    is_configured: bool
    email: Optional[str] = None # For mega configuration verification (redacted password)

# ==========================================
# Folder Schemas (Legacy/Existing)
# ==========================================

class FolderCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    parent_id: Optional[int] = None

class FolderRename(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)

class FolderResponse(BaseModel):
    id: int
    name: str
    parent_id: Optional[int]
    family_id: str
    created_at: datetime
    file_count: int = 0
    total_size_bytes: int = 0
    last_modified: Optional[datetime] = None

    class Config:
        from_attributes = True

# ==========================================
# File Schemas (Legacy/Existing)
# ==========================================

class FileRename(BaseModel):
    filename: str = Field(..., min_length=1, max_length=255)

class FileResponse(BaseModel):
    id: int
    filename: str
    file_type: str
    size_bytes: int
    uploader_id: Optional[int]
    uploader_email: Optional[str] = None
    folder_id: Optional[int]
    family_id: str
    upload_date: datetime
    storage_provider: str
    cloud_file_id: str
    cloud_link: Optional[str]

    class Config:
        from_attributes = True
