import io
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, BackgroundTasks, Request
from fastapi.responses import StreamingResponse, RedirectResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from database import get_db, SessionLocal
import models
import schemas
import auth
from storage import get_storage_provider
from sqlalchemy.orm import joinedload
from utils.audit import log_action
import os
import threading

_sync_locks = {}
_sync_locks_lock = threading.Lock()

def get_sync_lock(family_id: str):
    with _sync_locks_lock:
        if family_id not in _sync_locks:
            _sync_locks[family_id] = threading.Lock()
        return _sync_locks[family_id]

from config import (
    MEGA_EMAIL,
    MEGA_PASSWORD,
    GOOGLE_SERVICE_ACCOUNT_FILE,
    GOOGLE_FOLDER_ID
)
router = APIRouter(prefix="/api/files", tags=["Files"])

@router.get("", response_model=List[schemas.FileResponse])
def get_files(
    background_tasks: BackgroundTasks,
    folder_id: Optional[str] = None,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    query = db.query(models.File).options(joinedload(models.File.uploader)).filter(
        models.File.family_id == current_user.family_id,
        models.File.deleted_at == None
    )
    
    if folder_id is not None:
        if folder_id == "root" or folder_id == "":
            query = query.filter(models.File.folder_id == None)
        else:
            try:
                fid = int(folder_id)
                query = query.filter(models.File.folder_id == fid)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid folder_id format")
                
    files = query.all()
    
    shared_file_ids = {sl.file_id for sl in db.query(models.SharedLink.file_id).filter(models.SharedLink.family_id == current_user.family_id).all()}
    
    # Format files responses to include uploader email
    result = []
    for file in files:
        uploader_email = None
        if file.uploader:
            uploader_email = file.uploader.email
            
        result.append({
            "id": file.id,
            "filename": file.filename,
            "file_type": file.file_type,
            "size_bytes": file.size_bytes,
            "uploader_id": file.uploader_id,
            "uploader_email": uploader_email,
            "folder_id": file.folder_id,
            "family_id": file.family_id,
            "upload_date": file.upload_date,
            "storage_provider": file.storage_provider,
            "cloud_file_id": file.cloud_file_id,
            "cloud_link": file.cloud_link,
            "is_shared": file.id in shared_file_ids
        })
    
    family = db.query(models.Family).filter(models.Family.id == current_user.family_id).first()
    if family and family.storage_provider in ("google", "mega"):
        background_tasks.add_task(sync_fallback_to_primary, family.id)
        
    return result

def ensure_family_storage(family: models.Family, db: Session):
    # 1. Try Google Drive if configured
    if family.storage_provider == "google" and family.vault_folder_id:
        return
        
    has_google_config = False
    google_config = {}
    if family.storage_provider == "google" and family.storage_config and family.storage_config.get("folder_id"):
        google_config = family.storage_config
        has_google_config = True
    elif GOOGLE_FOLDER_ID:
        google_config = {"folder_id": GOOGLE_FOLDER_ID}
        has_google_config = True
        
    sa_exists = False
    sa_file = GOOGLE_SERVICE_ACCOUNT_FILE or "service-account.json"
    if not os.path.isabs(sa_file):
        backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        sa_file = os.path.join(backend_dir, sa_file)
    if os.path.exists(sa_file):
        sa_exists = True

    if has_google_config and sa_exists:
        try:
            from storage.google_drive_provider import GoogleDriveProvider
            provider = GoogleDriveProvider()
            vault_id = provider.ensure_vault_folder(family.id, google_config)
            
            family.storage_provider = "google"
            family.vault_folder_id = vault_id
            family.storage_config = google_config
            db.commit()
            return
        except Exception as google_err:
            print(f"Warning: Failed to initialize Google Drive Provider for family {family.id}: {str(google_err)}")

    # 2. Try Mega if configured
    if family.storage_provider == "mega" and family.vault_folder_id:
        return
        
    mega_config = {}
    has_mega_config = False
    if family.storage_provider == "mega" and family.storage_config and family.storage_config.get("email"):
        mega_config = family.storage_config
        has_mega_config = True
    elif MEGA_EMAIL and MEGA_PASSWORD:
        mega_config = {
            "email": MEGA_EMAIL,
            "password": MEGA_PASSWORD
        }
        has_mega_config = True

    if has_mega_config:
        try:
            from storage.mega_provider import MegaProvider
            provider = MegaProvider()
            vault_id = provider.ensure_vault_folder(family.id, mega_config)
            
            family.storage_provider = "mega"
            family.vault_folder_id = vault_id
            family.storage_config = mega_config
            db.commit()
            return
        except Exception as mega_err:
            print(f"Warning: Failed to initialize Mega Provider for family {family.id}: {str(mega_err)}")
            
    # 3. Fallback to Local Storage
    if family.storage_provider == "local" and family.vault_folder_id:
        return
        
    from storage.local import LocalStorageProvider
    local_prov = LocalStorageProvider()
    vault_id = local_prov.ensure_vault_folder(family.id, {})
    
    family.storage_provider = "local"
    family.vault_folder_id = vault_id
    family.storage_config = {"vault_folder_id": vault_id}
    db.commit()

def sync_fallback_to_primary(family_id: str):
    lock = get_sync_lock(family_id)
    if not lock.acquire(blocking=False):
        print(f"Background Sync: Sync already in progress for family {family_id}, skipping concurrent run.")
        return
    try:
        db = SessionLocal()
        try:
            family = db.query(models.Family).filter(models.Family.id == family_id).first()
            if not family or family.storage_provider not in ("google", "mega"):
                return
                
            primary_provider = family.storage_provider
            
            non_primary_files = db.query(models.File).filter(
                models.File.family_id == family_id,
                models.File.storage_provider != primary_provider,
                models.File.deleted_at == None
            ).all()
            
            if not non_primary_files:
                return
                
            print(f"Background Sync: Found {len(non_primary_files)} files to sync to primary provider '{primary_provider}' for family {family_id}")
            from storage import get_storage_provider
            
            primary_prov = get_storage_provider(primary_provider)
            primary_config = get_family_storage_config(family, db)
            
            for file in non_primary_files:
                filename = file.filename
                file_id = file.id
                old_provider_name = file.storage_provider
                old_cloud_file_id = file.cloud_file_id
                
                current_file = db.query(models.File).filter(models.File.id == file_id).first()
                if not current_file or current_file.deleted_at is not None:
                    continue

                try:
                    print(f"Syncing {filename} from {old_provider_name} to primary {primary_provider}...")
                    old_prov = get_storage_provider(old_provider_name)
                    
                    if old_provider_name == "local":
                        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "local_vault"))
                        old_config = {"vault_folder_id": os.path.join(base_dir, family_id)}
                    elif old_provider_name == "mega":
                        old_config = family.storage_config if family.storage_provider == "mega" else {}
                        if not old_config.get("email"):
                            from config import MEGA_EMAIL, MEGA_PASSWORD
                            old_config = {"email": MEGA_EMAIL, "password": MEGA_PASSWORD}
                    elif old_provider_name == "google":
                        old_config = family.storage_config if family.storage_provider == "google" else {}
                        if not old_config.get("folder_id"):
                            from config import GOOGLE_FOLDER_ID
                            old_config = {"folder_id": GOOGLE_FOLDER_ID}
                    else:
                        old_config = {}
                        
                    file_bytes = old_prov.download_file(old_config, old_cloud_file_id)
                    
                    upload_result = primary_prov.upload_file(
                        config=primary_config,
                        vault_folder_id=family.vault_folder_id,
                        filename=filename,
                        file_content=file_bytes,
                        mimetype=current_file.file_type
                    )
                    
                    try:
                        old_prov.delete_file(old_config, old_cloud_file_id)
                    except Exception as del_err:
                        print(f"Warning: Failed to delete old copy of {filename} on {old_provider_name}: {str(del_err)}")
                    
                    updated = db.query(models.File).filter(models.File.id == file_id).update({
                        "storage_provider": primary_provider,
                        "cloud_file_id": upload_result["cloud_file_id"],
                        "cloud_link": upload_result.get("cloud_link")
                    })
                    db.commit()
                    
                    if updated == 0:
                        print(f"File {filename} was deleted concurrently during sync. Cleaning up primary copy...")
                        primary_prov.delete_file(primary_config, upload_result["cloud_file_id"])
                    else:
                        print(f"Successfully synced {filename} to {primary_provider}.")
                except Exception as e:
                    db.rollback()
                    print(f"Failed to sync {filename}: {str(e)}")
        finally:
            db.close()
    finally:
        lock.release()


def get_family_storage_config(family: models.Family, db: Session) -> dict:
    ensure_family_storage(family, db)
    
    config = family.storage_config or {}
    if family.storage_provider == "local":
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "local_vault"))
        config = {"vault_folder_id": os.path.join(base_dir, family.id)}
    elif family.storage_provider == "mega":
        if MEGA_EMAIL and "email" not in config:
            config["email"] = MEGA_EMAIL
        if MEGA_PASSWORD and "password" not in config:
            config["password"] = MEGA_PASSWORD
    elif family.storage_provider == "google":
        if GOOGLE_FOLDER_ID and "folder_id" not in config:
            config["folder_id"] = GOOGLE_FOLDER_ID
    return config


def get_file_storage_config(file: models.File, family: models.Family, db: Session) -> dict:
    if file.storage_provider == "local":
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "local_vault"))
        return {"vault_folder_id": os.path.join(base_dir, family.id)}
    elif file.storage_provider == "mega":
        config = {}
        if family.storage_provider == "mega" and family.storage_config:
            config = family.storage_config.copy()
        if MEGA_EMAIL and "email" not in config:
            config["email"] = MEGA_EMAIL
        if MEGA_PASSWORD and "password" not in config:
            config["password"] = MEGA_PASSWORD
        return config
    elif file.storage_provider == "google":
        config = {}
        if family.storage_provider == "google" and family.storage_config:
            config = family.storage_config.copy()
        if GOOGLE_FOLDER_ID and "folder_id" not in config:
            config["folder_id"] = GOOGLE_FOLDER_ID
        return config
    return {}




@router.post("/upload", response_model=schemas.FileResponse, status_code=status.HTTP_201_CREATED)
async def upload_file(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    folder_id: Optional[int] = Form(None),
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    family = db.query(models.Family).filter(models.Family.id == current_user.family_id).first()
    if not family:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Family record not found")
        
    # Auto-initialize storage configuration if not set
    get_family_storage_config(family, db)

    # Validate parent folder if provided
    if folder_id is not None:
        folder = db.query(models.Folder).filter(
            models.Folder.id == folder_id,
            models.Folder.family_id == current_user.family_id
        ).first()
        if not folder:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target folder not found")

    # Enforce file type validation
    allowed_extensions = {".pdf", ".jpg", ".jpeg", ".png", ".docx", ".doc", ".xlsx", ".xls", ".txt"}
    _, ext = os.path.splitext(file.filename.lower())
    if ext not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File type not allowed. Supported formats: PDF, Word, Excel, Images, and TXT."
        )

    file_content = await file.read()
    file_size = len(file_content)

    # Enforce file size limit (50MB)
    MAX_FILE_SIZE = 50 * 1024 * 1024
    if file_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File size exceeds the maximum limit of 50MB."
        )

    # Enforce virus scanning check
    from utils.virus_scan import scan_file_for_viruses
    if not scan_file_for_viruses(file_content, file.filename):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Security error: Upload blocked. The file matches a known malware signature."
        )

    # Perform upload via storage provider abstraction. To ensure uploads are fast,
    # we always upload to 'local' storage first, and then sync to the primary cloud
    # provider ('google' or 'mega') in the background if configured.
    providers_cascade = ["local"]
    
    # Fallback to configured primary provider or other cloud providers if local storage fails.
    if family.storage_provider and family.storage_provider != "local":
        providers_cascade.append(family.storage_provider)
        
    sa_exists = False
    sa_file = GOOGLE_SERVICE_ACCOUNT_FILE or "service-account.json"
    if not os.path.isabs(sa_file):
        backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        sa_file = os.path.join(backend_dir, sa_file)
    if os.path.exists(sa_file):
        sa_exists = True
        
    if "google" not in providers_cascade and sa_exists and (GOOGLE_FOLDER_ID or (family.storage_provider == "google" and family.storage_config and family.storage_config.get("folder_id"))):
        providers_cascade.append("google")
        
    if "mega" not in providers_cascade and (MEGA_EMAIL and MEGA_PASSWORD):
        providers_cascade.append("mega")

    upload_result = None
    used_provider = None
    last_error = None
    
    for provider_name in providers_cascade:
        try:
            if provider_name == family.storage_provider:
                storage_config = get_family_storage_config(family, db)
                vault_folder_id = family.vault_folder_id
            else:
                if provider_name == "google":
                    storage_config = family.storage_config if family.storage_provider == "google" else {}
                    if not storage_config.get("folder_id") and GOOGLE_FOLDER_ID:
                        storage_config = {"folder_id": GOOGLE_FOLDER_ID}
                elif provider_name == "mega":
                    storage_config = family.storage_config if family.storage_provider == "mega" else {}
                    if not storage_config.get("email") and MEGA_EMAIL:
                        storage_config = {"email": MEGA_EMAIL, "password": MEGA_PASSWORD}
                elif provider_name == "local":
                    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "local_vault"))
                    storage_config = {"vault_folder_id": os.path.join(base_dir, family.id)}
                else:
                    storage_config = {}
                    
                prov_instance = get_storage_provider(provider_name)
                vault_folder_id = prov_instance.ensure_vault_folder(family.id, storage_config)
            
            prov_instance = get_storage_provider(provider_name)
            upload_result = prov_instance.upload_file(
                config=storage_config,
                vault_folder_id=vault_folder_id,
                filename=file.filename,
                file_content=file_content,
                mimetype=file.content_type
            )
            used_provider = provider_name
            break
        except Exception as e:
            print(f"Warning: Upload failed for provider '{provider_name}': {str(e)}")
            last_error = e
            
    if not upload_result:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Upload failed across all storage providers. Last error: {str(last_error)}"
        )
        
    if family.storage_provider in ("google", "mega") and used_provider != family.storage_provider:
        background_tasks.add_task(sync_fallback_to_primary, family.id)

    # If Google OAuth token refreshed during the request, update database config
    if "updated_config" in upload_result:
        family.storage_config = upload_result["updated_config"]
        db.commit()


    # Save metadata in database
    new_file = models.File(
        filename=file.filename,
        file_type=file.content_type or "application/octet-stream",
        size_bytes=file_size,
        uploader_id=current_user.id,
        folder_id=folder_id,
        family_id=current_user.family_id,
        storage_provider=used_provider,
        cloud_file_id=upload_result["cloud_file_id"],
        cloud_link=upload_result.get("cloud_link")
    )
    
    db.add(new_file)
    db.commit()
    db.refresh(new_file)
    
    # Audit log
    ip = request.client.host if request.client else "127.0.0.1"
    log_action(db, "UPLOAD_FILE", current_user.id, current_user.family_id, ip, f"Uploaded file: {new_file.filename} ({new_file.size_bytes} bytes)")
    
    return {
        "id": new_file.id,
        "filename": new_file.filename,
        "file_type": new_file.file_type,
        "size_bytes": new_file.size_bytes,
        "uploader_id": new_file.uploader_id,
        "uploader_email": current_user.email,
        "folder_id": new_file.folder_id,
        "family_id": new_file.family_id,
        "upload_date": new_file.upload_date,
        "storage_provider": new_file.storage_provider,
        "cloud_file_id": new_file.cloud_file_id,
        "cloud_link": new_file.cloud_link
    }

@router.get("/{file_id}/download")
def download_file(
    file_id: int,
    request: Request,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    file = db.query(models.File).filter(
        models.File.id == file_id,
        models.File.family_id == current_user.family_id,
        models.File.deleted_at == None
    ).first()
    
    if not file:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
        
    family = db.query(models.Family).filter(models.Family.id == current_user.family_id).first()
    
    # Audit log
    ip = request.client.host if request.client else "127.0.0.1"
    log_action(db, "DOWNLOAD_FILE", current_user.id, current_user.family_id, ip, f"Downloaded file: {file.filename}")
    
    # Try to get direct redirect download URL for cloud providers (only MEGA, as Google blocks direct browser redirects)
    if file.storage_provider == "mega":
        try:
            provider = get_storage_provider(file.storage_provider)
            config = get_file_storage_config(file, family, db)
            if hasattr(provider, "get_direct_download_url"):
                direct_url = provider.get_direct_download_url(config, file.cloud_file_id)
                if direct_url:
                    return RedirectResponse(url=direct_url)
        except Exception as e:
            print(f"Warning: Failed to get direct download URL: {str(e)}. Falling back to streaming.")

    try:
        provider = get_storage_provider(file.storage_provider)
        config = get_file_storage_config(file, family, db)
        file_bytes = provider.download_file(config, file.cloud_file_id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve file from cloud storage: {str(e)}"
        )
    return StreamingResponse(
        io.BytesIO(file_bytes),
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{file.filename}"',
            "Access-Control-Expose-Headers": "Content-Disposition"
        }
    )

@router.get("/{file_id}/preview")
def preview_file(
    file_id: int,
    request: Request,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    file = db.query(models.File).filter(
        models.File.id == file_id,
        models.File.family_id == current_user.family_id,
        models.File.deleted_at == None
    ).first()
    
    if not file:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
        
    family = db.query(models.Family).filter(models.Family.id == current_user.family_id).first()
    
    # Audit log
    ip = request.client.host if request.client else "127.0.0.1"
    log_action(db, "PREVIEW_FILE", current_user.id, current_user.family_id, ip, f"Previewed file: {file.filename}")
    


    try:
        provider = get_storage_provider(file.storage_provider)
        config = get_file_storage_config(file, family, db)
        file_bytes = provider.download_file(config, file.cloud_file_id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve file from cloud storage: {str(e)}"
        )
    return StreamingResponse(
        io.BytesIO(file_bytes),
        media_type=file.file_type or "application/octet-stream",
        headers={"Content-Disposition": f'inline; filename="{file.filename}"'}
    )

@router.put("/{file_id}", response_model=schemas.FileResponse)
def rename_file(
    file_id: int,
    file_in: schemas.FileRename,
    request: Request,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    file = db.query(models.File).filter(
        models.File.id == file_id,
        models.File.family_id == current_user.family_id,
        models.File.deleted_at == None
    ).first()
    
    if not file:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
        
    # Enforce role logic: members can only rename their own uploads
    if current_user.role != "admin" and file.uploader_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to rename files uploaded by other family members"
        )
        
    family = db.query(models.Family).filter(models.Family.id == current_user.family_id).first()
    old_name = file.filename
    new_name = file_in.filename.strip()
    
    # Rename in the cloud
    try:
        provider = get_storage_provider(file.storage_provider)
        config = get_file_storage_config(file, family, db)
        provider.rename_file(config, file.cloud_file_id, new_name)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to rename file in cloud storage: {str(e)}"
        )
        
    # Update local DB metadata
    file.filename = new_name
    if file.storage_provider == "local":
        file.cloud_file_id = new_name
    db.commit()
    db.refresh(file)
    
    # Audit log
    ip = request.client.host if request.client else "127.0.0.1"
    log_action(db, "RENAME_FILE", current_user.id, current_user.family_id, ip, f"Renamed file '{old_name}' to '{new_name}'")
    
    uploader_email = None
    if file.uploader:
        uploader_email = file.uploader.email
        
    return {
        "id": file.id,
        "filename": file.filename,
        "file_type": file.file_type,
        "size_bytes": file.size_bytes,
        "uploader_id": file.uploader_id,
        "uploader_email": uploader_email,
        "folder_id": file.folder_id,
        "family_id": file.family_id,
        "upload_date": file.upload_date,
        "storage_provider": file.storage_provider,
        "cloud_file_id": file.cloud_file_id,
        "cloud_link": file.cloud_link
    }

@router.delete("/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_file(
    file_id: int,
    request: Request,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    file = db.query(models.File).filter(
        models.File.id == file_id,
        models.File.family_id == current_user.family_id,
        models.File.deleted_at == None
    ).first()
    
    if not file:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
        
    # Enforce role logic: members can only delete their own uploads
    if current_user.role != "admin" and file.uploader_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to delete files uploaded by other family members"
        )
        
    from sqlalchemy.sql import func
    file.deleted_at = func.now()
    db.commit()
    
    # Audit log
    ip = request.client.host if request.client else "127.0.0.1"
    log_action(db, "DELETE_FILE", current_user.id, current_user.family_id, ip, f"Soft-deleted file: {file.filename}")
    
    return None

@router.patch("/{file_id}/move", response_model=schemas.FileResponse)
def move_file(
    file_id: int,
    file_in: schemas.FileMove,
    request: Request,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    file = db.query(models.File).options(joinedload(models.File.uploader)).filter(
        models.File.id == file_id,
        models.File.family_id == current_user.family_id,
        models.File.deleted_at == None
    ).first()
    
    if not file:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
        
    # Verify destination folder exists
    if file_in.folder_id is not None:
        folder = db.query(models.Folder).filter(
            models.Folder.id == file_in.folder_id,
            models.Folder.family_id == current_user.family_id,
            models.Folder.deleted_at == None
        ).first()
        if not folder:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Destination folder not found")

    file.folder_id = file_in.folder_id
    db.commit()
    db.refresh(file)
    
    # Audit log
    ip = request.client.host if request.client else "127.0.0.1"
    dest_name = "Root" if file.folder_id is None else f"Folder ID {file.folder_id}"
    log_action(db, "MOVE_FILE", current_user.id, current_user.family_id, ip, f"Moved file '{file.filename}' to '{dest_name}'")
    
    uploader_email = None
    if file.uploader:
        uploader_email = file.uploader.email
        
    return {
        "id": file.id,
        "filename": file.filename,
        "file_type": file.file_type,
        "size_bytes": file.size_bytes,
        "uploader_id": file.uploader_id,
        "uploader_email": uploader_email,
        "folder_id": file.folder_id,
        "family_id": file.family_id,
        "upload_date": file.upload_date,
        "storage_provider": file.storage_provider,
        "cloud_file_id": file.cloud_file_id,
        "cloud_link": file.cloud_link
    }
