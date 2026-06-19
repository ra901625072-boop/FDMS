import secrets
import string
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from database import get_db
import models
import schemas
import auth

router = APIRouter(prefix="/api/family", tags=["Family"])

def generate_family_secret_code() -> str:
    # 8 uppercase alphanumeric characters
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(8))

@router.post("/setup", response_model=schemas.FamilySetupResponse)
def setup_family(
    setup_data: schemas.FamilySetup,
    current_user: models.User = Depends(auth.get_admin_user),
    db: Session = Depends(get_db)
):
    # Ensure this admin doesn't already have a family (optional, but good practice)
    existing_family = db.query(models.Family).filter(models.Family.admin_id == current_user.id).first()
    if existing_family:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You already administer a family."
        )

    # Generate an ID for the family
    family_id = "".join(secrets.choice(string.ascii_lowercase + string.digits) for _ in range(12))

    plaintext_code = generate_family_secret_code()
    # Format code with hyphen for better UX (e.g. XXXX-XXXX)
    formatted_plaintext = f"{plaintext_code[:4]}-{plaintext_code[4:]}"
    hashed_code = auth.get_password_hash(plaintext_code)

    new_family = models.Family(
        id=family_id,
        name=setup_data.name,
        admin_id=current_user.id,
        secret_code_hash=hashed_code,
        max_members=setup_data.max_members
    )
    db.add(new_family)
    db.flush()

    # Add the admin as a family member as well
    admin_member = models.FamilyMember(
        family_id=family_id,
        user_id=current_user.id,
        role="admin"
    )
    db.add(admin_member)
    db.commit()

    return schemas.FamilySetupResponse(
        family_id=family_id,
        name=setup_data.name,
        secret_code=formatted_plaintext,
        max_members=setup_data.max_members
    )

@router.get("/members", response_model=List[schemas.FamilyMemberResponse])
def get_family_members(
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    # Find which family the current user belongs to
    membership = db.query(models.FamilyMember).filter(models.FamilyMember.user_id == current_user.id).first()
    if not membership:
        raise HTTPException(status_code=404, detail="You do not belong to any family.")

    members = db.query(models.FamilyMember).filter(models.FamilyMember.family_id == membership.family_id).all()
    return members
