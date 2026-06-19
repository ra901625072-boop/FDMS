import io
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from database import get_db, SessionLocal
import models
import schemas
import auth
from storage import get_storage_provider
from sqlalchemy.orm import joinedload
import os
from config import (
    MEGA_EMAIL,
    MEGA_PASSWORD
)
router = APIRouter(prefix="/api/files", tags=["Files"])

@router.get("", response_model=List[schemas.FileResponse])
def get_files(
    background_tasks: BackgroundTasks,
    folder_id: Optional[str] = None,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    query = db.query(models.File).options(joinedload(models.File.uploader)).filter(models.File.family_id == current_user.family_id)
    
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
            "cloud_link": file.cloud_link
        })
    
    family = db.query(models.Family).filter(models.Family.id == current_user.family_id).first()
    if family and family.storage_provider == "mega":
        background_tasks.add_task(sync_local_to_mega, family.id)
        
    return result

def ensure_family_storage(family: models.Family, db: Session):
    if family.storage_provider == "mega" and family.vault_folder_id:
        return
        
    if MEGA_EMAIL and MEGA_PASSWORD:
        try:
            from storage.mega_provider import MegaProvider
            provider = MegaProvider()
            mega_config = {
                "email": MEGA_EMAIL,
                "password": MEGA_PASSWORD
            }
            vault_id = provider.ensure_vault_folder(family.id, mega_config)
            
            family.storage_provider = "mega"
            family.vault_folder_id = vault_id
            family.storage_config = mega_config
            db.commit()
            return
        except Exception as mega_err:
            print(f"Warning: Failed to initialize Mega Provider for family {family.id}: {str(mega_err)}")
            
    if family.storage_provider == "local" and family.vault_folder_id:
        return
        
    # Fallback to local storage
    from storage.local import LocalStorageProvider
    local_prov = LocalStorageProvider()
    vault_id = local_prov.ensure_vault_folder(family.id, {})
    
    family.storage_provider = "local"
    family.vault_folder_id = vault_id
    family.storage_config = {"vault_folder_id": vault_id}
    db.commit()

def sync_local_to_mega(family_id: str):
    db = SessionLocal()
    try:
        family = db.query(models.Family).filter(models.Family.id == family_id).first()
        if not family or family.storage_provider != "mega":
            return
            
        local_files = db.query(models.File).filter(
            models.File.family_id == family_id,
            models.File.storage_provider == "local"
        ).all()
        
        if not local_files:
            return
            
        print(f"Background Sync: Found {len(local_files)} local files to sync to MEGA for family {family_id}")
        from storage.mega_provider import MegaProvider
        from storage.local import LocalStorageProvider
        
        mega_prov = MegaProvider()
        local_prov = LocalStorageProvider()
        mega_config = family.storage_config
        
        import os
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "local_vault"))
        local_config = {"vault_folder_id": os.path.join(base_dir, family.id)}

        for file in local_files:
            filename = file.filename
            file_id = file.id
            cloud_file_id = file.cloud_file_id
            
            # verify it still exists before starting heavy sync
            current_file = db.query(models.File).filter(models.File.id == file_id).first()
            if not current_file:
                continue

            try:
                print(f"Syncing {filename}...")
                file_bytes = local_prov.download_file(local_config, cloud_file_id)
                
                upload_result = mega_prov.upload_file(
                    config=mega_config,
                    vault_folder_id=family.vault_folder_id,
                    filename=filename,
                    file_content=file_bytes,
                    mimetype=current_file.file_type
                )
                
                local_prov.delete_file(local_config, cloud_file_id)
                
                # Update using query.update to prevent StaleDataError
                updated = db.query(models.File).filter(models.File.id == file_id).update({
                    "storage_provider": "mega",
                    "cloud_file_id": upload_result["cloud_file_id"],
                    "cloud_link": upload_result.get("cloud_link")
                })
                db.commit()
                
                if updated == 0:
                    print(f"File {filename} was deleted concurrently during sync. Cleaning up MEGA copy...")
                    mega_prov.delete_file(mega_config, upload_result["cloud_file_id"])
                else:
                    print(f"Successfully synced {filename} to MEGA.")
            except Exception as e:
                db.rollback()
                print(f"Failed to sync {filename}: {str(e)}")
    finally:
        db.close()


def get_family_storage_config(family: models.Family, db: Session) -> dict:
    ensure_family_storage(family, db)
    
    config = family.storage_config or {}
    if family.storage_provider == "local":
        import os
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "local_vault"))
        config = {"vault_folder_id": os.path.join(base_dir, family.id)}
    if family.storage_provider == "mega":
        if MEGA_EMAIL and "email" not in config:
            config["email"] = MEGA_EMAIL
        if MEGA_PASSWORD and "password" not in config:
            config["password"] = MEGA_PASSWORD
    return config


@router.post("/upload", response_model=schemas.FileResponse, status_code=status.HTTP_201_CREATED)
async def upload_file(
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

    file_content = await file.read()
    file_size = len(file_content)

    # Perform upload via storage provider abstraction
    used_provider = family.storage_provider
    try:
        storage_config = get_family_storage_config(family, db)
        provider = get_storage_provider(family.storage_provider)
        upload_result = provider.upload_file(
            config=storage_config,
            vault_folder_id=family.vault_folder_id,
            filename=file.filename,
            file_content=file_content,
            mimetype=file.content_type
        )
        if used_provider == "mega":
            background_tasks.add_task(sync_local_to_mega, family.id)
    except Exception as e:
        print(f"Warning: Primary storage upload failed: {str(e)}. Falling back to local storage.")
        from storage.local import LocalStorageProvider
        local_prov = LocalStorageProvider()
        
        import os
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "local_vault"))
        local_config = {"vault_folder_id": os.path.join(base_dir, family.id)}
        local_vault_id = local_prov.ensure_vault_folder(family.id, local_config)
        
        upload_result = local_prov.upload_file(
            config=local_config,
            vault_folder_id=local_vault_id,
            filename=file.filename,
            file_content=file_content,
            mimetype=file.content_type
        )
        used_provider = "local"

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
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    file = db.query(models.File).filter(
        models.File.id == file_id,
        models.File.family_id == current_user.family_id
    ).first()
    
    if not file:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
        
    family = db.query(models.Family).filter(models.Family.id == current_user.family_id).first()
    
    try:
        provider = get_storage_provider(file.storage_provider)
        config = get_family_storage_config(family, db)
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
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    file = db.query(models.File).filter(
        models.File.id == file_id,
        models.File.family_id == current_user.family_id
    ).first()
    
    if not file:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
        
    family = db.query(models.Family).filter(models.Family.id == current_user.family_id).first()
    
    try:
        provider = get_storage_provider(file.storage_provider)
        config = get_family_storage_config(family, db)
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
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    file = db.query(models.File).filter(
        models.File.id == file_id,
        models.File.family_id == current_user.family_id
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
    new_name = file_in.filename.strip()
    
    # Rename in the cloud
    try:
        provider = get_storage_provider(file.storage_provider)
        config = get_family_storage_config(family, db)
        provider.rename_file(config, file.cloud_file_id, new_name)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to rename file in cloud storage: {str(e)}"
        )
        
    # Update local DB metadata
    file.filename = new_name
    db.commit()
    db.refresh(file)
    
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
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    file = db.query(models.File).filter(
        models.File.id == file_id,
        models.File.family_id == current_user.family_id
    ).first()
    
    if not file:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
        
    # Enforce role logic: members can only delete their own uploads
    if current_user.role != "admin" and file.uploader_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to delete files uploaded by other family members"
        )
        
    family = db.query(models.Family).filter(models.Family.id == current_user.family_id).first()
    
    # Delete from the cloud storage
    try:
        provider = get_storage_provider(file.storage_provider)
        config = get_family_storage_config(family, db)
        provider.delete_file(config, file.cloud_file_id)
    except Exception as e:
        # We will log the warning and delete from the database anyway to prevent broken sync
        print(f"Warning: Failed to delete file {file.cloud_file_id} from cloud: {str(e)}")
            
    db.delete(file)
    db.commit()
    return None
