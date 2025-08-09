from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional
import logging

from src.database.connection import get_db_session
from src.services.image_resource_service import ImageResourceService
from src.models.image_resource import (
    ImageResourceCreate,
    ImageResourceUpdate,
    ImageResourceResponse,
    ImageResourceList
)

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/image-resources/", response_model=ImageResourceList)
def get_image_resources(
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    search_query: Optional[str] = Query(None, description="Search query for description, tags, or search_query"),
    source: Optional[str] = Query(None, description="Filter by source (e.g., pexels, unsplash)"),
    download_status: Optional[str] = Query(None, description="Filter by download status"),
    is_downloaded: Optional[bool] = Query(None, description="Filter by download status"),
    db: Session = Depends(get_db_session)
):
    """Get paginated list of image resources with optional filters"""
    try:
        service = ImageResourceService(db)
        return service.list_image_resources(
            page=page,
            per_page=per_page,
            search_query=search_query,
            source=source,
            download_status=download_status,
            is_downloaded=is_downloaded
        )
    except Exception as e:
        logger.error(f"Error getting image resources: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/image-resources/{image_id}", response_model=ImageResourceResponse)
def get_image_resource(
    image_id: str,
    db: Session = Depends(get_db_session)
):
    """Get a specific image resource by ID"""
    try:
        service = ImageResourceService(db)
        image_resource = service.get_image_resource(image_id)
        
        if not image_resource:
            raise HTTPException(status_code=404, detail="Image resource not found")
        
        return image_resource
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting image resource: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/image-resources/check-url/{url:path}")
def check_url(
    url: str,
    db: Session = Depends(get_db_session)
):
    """Check if an image URL already exists in the database"""
    try:
        service = ImageResourceService(db)
        image_resource = service.get_image_resource_by_url(url)
        
        return {
            "url": url,
            "exists": image_resource is not None,
            "image_resource": image_resource
        }
    except Exception as e:
        logger.error(f"Error checking URL: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/image-resources/", response_model=ImageResourceResponse)
def create_image_resource(
    image_resource: ImageResourceCreate,
    db: Session = Depends(get_db_session)
):
    """Create a new image resource"""
    try:
        service = ImageResourceService(db)
        
        # Check if URL already exists
        existing = service.get_image_resource_by_url(str(image_resource.url))
        if existing:
            raise HTTPException(status_code=400, detail="Image URL already exists")
        
        return service.create_image_resource(image_resource)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating image resource: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.put("/image-resources/{image_id}", response_model=ImageResourceResponse)
def update_image_resource(
    image_id: str,
    image_resource: ImageResourceUpdate,
    db: Session = Depends(get_db_session)
):
    """Update an existing image resource"""
    try:
        service = ImageResourceService(db)
        updated_resource = service.update_image_resource(image_id, image_resource)
        
        if not updated_resource:
            raise HTTPException(status_code=404, detail="Image resource not found")
        
        return updated_resource
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating image resource: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.delete("/image-resources/{image_id}")
def delete_image_resource(
    image_id: str,
    db: Session = Depends(get_db_session)
):
    """Delete an image resource"""
    try:
        service = ImageResourceService(db)
        deleted = service.delete_image_resource(image_id)
        
        if not deleted:
            raise HTTPException(status_code=404, detail="Image resource not found")
        
        return {"message": "Image resource deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting image resource: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/image-resources/bulk", response_model=list[ImageResourceResponse])
def bulk_create_image_resources(
    image_resources: list[ImageResourceCreate],
    db: Session = Depends(get_db_session)
):
    """Bulk create multiple image resources"""
    try:
        service = ImageResourceService(db)
        return service.bulk_create_image_resources(image_resources)
    except Exception as e:
        logger.error(f"Error bulk creating image resources: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.patch("/image-resources/{image_id}/download-status")
def update_download_status(
    image_id: str,
    status: str,
    error_message: Optional[str] = None,
    db: Session = Depends(get_db_session)
):
    """Update the download status of an image resource"""
    try:
        service = ImageResourceService(db)
        updated_resource = service.update_download_status(image_id, status, error_message)
        
        if not updated_resource:
            raise HTTPException(status_code=404, detail="Image resource not found")
        
        return updated_resource
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating download status: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/image-resources/statistics")
def get_image_resource_statistics(
    db: Session = Depends(get_db_session)
):
    """Get statistics about image resources"""
    try:
        service = ImageResourceService(db)
        return service.get_statistics()
    except Exception as e:
        logger.error(f"Error getting statistics: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

