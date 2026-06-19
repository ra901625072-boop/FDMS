import secrets
import string
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from database import get_db
import models
import schemas
import auth

router = APIRouter(prefix="/api/auth", tags=["Authentication"])

# Simple in-memory rate limiter
# Structure: { ip_address: [timestamp1, timestamp2, ...] }
rate_limit_store = {}
RATE_LIMIT_MAX = 5
RATE_LIMIT_WINDOW = timedelta(minutes=10)

def check_rate_limit(ip: str):
    now = datetime.now(timezone.utc)
    # Clean up old entries
    if ip in rate_limit_store:
        rate_limit_store[ip] = [ts for ts in rate_limit_store[ip] if now - ts < RATE_LIMIT_WINDOW]
    else:
        rate_limit_store[ip] = []
        
    if len(rate_limit_store[ip]) >= RATE_LIMIT_MAX:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many family login attempts. Please try again in 10 minutes."
        )
    rate_limit_store[ip].append(now)

@router.post("/register", response_model=schemas.UserResponse, status_code=status.HTTP_201_CREATED)
def register(user_in: schemas.UserRegister, db: Session = Depends(get_db)):
    # Check if user already exists
    existing_user = db.query(models.User).filter(models.User.email == user_in.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email is already registered."
        )

    existing_username = db.query(models.User).filter(models.User.username == user_in.username).first()
    if existing_username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this username is already registered."
        )

    # Hash the password
    hashed_pwd = auth.get_password_hash(user_in.password)
    
    # Create new user as admin
    new_user = models.User(
        username=user_in.username,
        email=user_in.email,
        password_hash=hashed_pwd,
        role="admin"
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@router.post("/login", response_model=schemas.Token)
def login(credentials: schemas.UserLogin, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == credentials.email).first()
    if not user or not user.password_hash or not auth.verify_password(credentials.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = auth.create_access_token(
        data={
            "sub": user.email,
            "id": user.id,
            "role": user.role,
        }
    )
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/family-login", response_model=schemas.Token)
def family_login(request: Request, login_in: schemas.FamilyLogin, db: Session = Depends(get_db)):
    # Rate Limiting: 5 attempts / 10 min per IP
    ip = request.client.host if request.client else "127.0.0.1"
    check_rate_limit(ip)
    
    # 1. All fields filled (Handled by Pydantic schema validation)
    # 2. Hash the entered code -> look up matching family record
    code_to_check = login_in.secret_code.replace("-", "").upper()
    families = db.query(models.Family).all()
    matched_family = None
    for f in families:
        if auth.verify_password(code_to_check, f.secret_code_hash):
            matched_family = f
            break
            
    if not matched_family:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid secret code. Please check with your family admin."
        )

    # 3. Check code has not expired
    if matched_family.expires_at and matched_family.expires_at < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="This family code has expired. Ask your admin to generate a new one."
        )

    # 4. Check current member count < max_members
    current_members = db.query(models.FamilyMember).filter(models.FamilyMember.family_id == matched_family.id).count()
    if current_members >= matched_family.max_members:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This family is full. Contact your family admin."
        )

    # 5. Check this email is not already a member of this family
    existing_user = db.query(models.User).filter(models.User.email == login_in.email).first()
    if existing_user:
        # User exists, verify they aren't already in this family
        membership = db.query(models.FamilyMember).filter(
            models.FamilyMember.family_id == matched_family.id,
            models.FamilyMember.user_id == existing_user.id
        ).first()
        if membership:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You are already a member of this family."
            )
        user = existing_user
    else:
        # Create new user record
        user = models.User(
            username=login_in.username,
            email=login_in.email,
            password_hash=None,
            role="member"
        )
        db.add(user)
        db.flush() # flush to get user.id

    # Insert into family_members
    new_member = models.FamilyMember(
        family_id=matched_family.id,
        user_id=user.id,
        role="member"
    )
    db.add(new_member)
    db.commit()
    db.refresh(user)

    # Generate token
    access_token = auth.create_access_token(
        data={
            "sub": user.email,
            "id": user.id,
            "role": user.role,
        }
    )
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/me", response_model=schemas.UserResponse)
def get_me(current_user: models.User = Depends(auth.get_current_user)):
    return current_user
