from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from database import get_db
import models
import schemas
import auth
from config import BACKEND_URL, FRONTEND_URL
from storage import get_storage_provider

router = APIRouter(prefix="/api/storage", tags=["Storage Configuration"])

@router.get("/config", response_model=schemas.StorageConfigResponse)
def get_storage_config(
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    family = db.query(models.Family).filter(models.Family.id == current_user.family_id).first()
    if not family:
        raise HTTPException(status_code=404, detail="Family record not found")
        
    from routers.files import get_family_storage_config
    get_family_storage_config(family, db)
    return {
        "storage_provider": family.storage_provider,
        "is_configured": True,
        "email": None
    }


@router.post("/config/mega", response_model=schemas.StorageConfigResponse)
def setup_mega(
    setup_in: schemas.StorageSetupMega,
    current_user: models.User = Depends(auth.get_admin_user),
    db: Session = Depends(get_db)
):
    family = db.query(models.Family).filter(models.Family.id == current_user.family_id).first()
    if not family:
        raise HTTPException(status_code=404, detail="Family record not found")

    config = {
        "email": setup_in.email,
        "password": setup_in.password
    }

    try:
        provider = get_storage_provider("mega")
        # 1. Verify login works
        provider.verify_credentials(config)
        # 2. Ensure vault folder exists
        vault_id = provider.ensure_vault_folder(family.id, config)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Mega Configuration Error: {str(e)}"
        )

    # Save to database
    family.storage_provider = "mega"
    family.storage_config = config
    family.vault_folder_id = vault_id
    db.commit()
    
    return {
        "storage_provider": "mega",
        "is_configured": True,
        "email": setup_in.email
    }

