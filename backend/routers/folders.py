from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from database import get_db
import models
import schemas
import auth
from storage import get_storage_provider
from sqlalchemy import func
from routers.files import get_family_storage_config

router = APIRouter(prefix="/api/folders", tags=["Folders"])

@router.get("", response_model=List[schemas.FolderResponse])
def get_folders(
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    query_results = db.query(
        models.Folder,
        func.count(models.File.id).label('file_count'),
        func.coalesce(func.sum(models.File.size_bytes), 0).label('total_size'),
        func.max(models.File.upload_date).label('last_modified_file')
    ).outerjoin(
        models.File, models.File.folder_id == models.Folder.id
    ).filter(
        models.Folder.family_id == current_user.family_id
    ).group_by(models.Folder.id).all()
    
    result = []
    for folder, file_count, total_size, last_modified_file in query_results:
        last_modified = folder.created_at
        if last_modified_file and last_modified_file > last_modified:
            last_modified = last_modified_file
            
        result.append({
            "id": folder.id,
            "name": folder.name,
            "parent_id": folder.parent_id,
            "family_id": folder.family_id,
            "created_at": folder.created_at,
            "file_count": file_count,
            "total_size_bytes": total_size,
            "last_modified": last_modified
        })
        
    return result

@router.post("", response_model=schemas.FolderResponse, status_code=status.HTTP_201_CREATED)
def create_folder(
    folder_in: schemas.FolderCreate,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    # If parent folder is specified, verify it exists and belongs to the family
    if folder_in.parent_id is not None:
        parent = db.query(models.Folder).filter(
            models.Folder.id == folder_in.parent_id,
            models.Folder.family_id == current_user.family_id
        ).first()
        if not parent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Parent folder not found"
            )

    new_folder = models.Folder(
        name=folder_in.name.strip(),
        parent_id=folder_in.parent_id,
        family_id=current_user.family_id
    )
    
    db.add(new_folder)
    db.commit()
    db.refresh(new_folder)
    
    # Return formatted response
    return {
        "id": new_folder.id,
        "name": new_folder.name,
        "parent_id": new_folder.parent_id,
        "family_id": new_folder.family_id,
        "created_at": new_folder.created_at,
        "file_count": 0,
        "total_size_bytes": 0,
        "last_modified": new_folder.created_at
    }

@router.put("/{folder_id}", response_model=schemas.FolderResponse)
def rename_folder(
    folder_id: int,
    folder_in: schemas.FolderRename,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    folder = db.query(models.Folder).filter(
        models.Folder.id == folder_id,
        models.Folder.family_id == current_user.family_id
    ).first()
    
    if not folder:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Folder not found"
        )
        
    folder.name = folder_in.name.strip()
    db.commit()
    db.refresh(folder)
    
    # Calculate stats efficiently
    stats = db.query(
        func.count(models.File.id).label('file_count'),
        func.coalesce(func.sum(models.File.size_bytes), 0).label('total_size'),
        func.max(models.File.upload_date).label('last_modified_file')
    ).filter(models.File.folder_id == folder.id).first()
    
    file_count = stats.file_count or 0
    total_size = stats.total_size or 0
    last_modified = folder.created_at
    if stats.last_modified_file and stats.last_modified_file > last_modified:
        last_modified = stats.last_modified_file

    return {
        "id": folder.id,
        "name": folder.name,
        "parent_id": folder.parent_id,
        "family_id": folder.family_id,
        "created_at": folder.created_at,
        "file_count": file_count,
        "total_size_bytes": total_size,
        "last_modified": last_modified
    }

def delete_folder_recursive(folder_id: int, family: models.Family, db: Session):
    # 1. Recurse into subfolders
    subfolders = db.query(models.Folder).filter(models.Folder.parent_id == folder_id).all()
    for sub in subfolders:
        delete_folder_recursive(sub.id, family, db)
        
    # 2. Delete files in this folder from cloud and DB
    files = db.query(models.File).filter(models.File.folder_id == folder_id).all()
    if files and family.storage_provider:
        try:
            storage_config = get_family_storage_config(family, db)
            provider = get_storage_provider(family.storage_provider)
            for file in files:
                try:
                    provider.delete_file(storage_config, file.cloud_file_id)

                except Exception as e:
                    # Log but continue to ensure DB cleanup
                    print(f"Warning: Failed to delete cloud file {file.cloud_file_id}: {str(e)}")
                db.delete(file)
        except Exception as e:
            print(f"Warning: Failed to get storage provider: {str(e)}")
            # Even if provider fails, delete file metadata to prevent dead references
            for file in files:
                db.delete(file)
    else:
        for file in files:
            db.delete(file)
            
    # 3. Delete folder record
    folder = db.query(models.Folder).filter(models.Folder.id == folder_id).first()
    if folder:
        db.delete(folder)

@router.delete("/{folder_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_folder(
    folder_id: int,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    folder = db.query(models.Folder).filter(
        models.Folder.id == folder_id,
        models.Folder.family_id == current_user.family_id
    ).first()
    
    if not folder:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Folder not found"
        )
        
    family = db.query(models.Family).filter(models.Family.id == current_user.family_id).first()
    
    # Execute recursive delete
    delete_folder_recursive(folder_id, family, db)
    db.commit()
    return None
