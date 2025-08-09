from sqlalchemy.orm import Session
from sqlalchemy import select, update, delete, func, and_, or_
from sqlalchemy.orm import selectinload
from typing import List, Optional, Dict, Any
import json
import logging
from datetime import datetime

from src.models.image_resource import (
    ImageResourceModel,
    ImageResourceCreate,
    ImageResourceUpdate,
    ImageResourceResponse,
    ImageResourceList
)

logger = logging.getLogger(__name__)

class ImageResourceService:
    def __init__(self, db_session: Session):
        self.db = db_session
    
    def create_image_resource(self, image_data: ImageResourceCreate) -> ImageResourceResponse:
        """Create a new image resource"""
        try:
            # Convert tags list to JSON string if provided
            tags_json = None
            if image_data.tags:
                tags_json = json.dumps(image_data.tags)
            
            # Create new image resource
            db_image = ImageResourceModel(
                url=str(image_data.url),
                filename=image_data.filename,
                file_path=image_data.file_path,
                file_size=image_data.file_size,
                width=image_data.width,
                height=image_data.height,
                format=image_data.format,
                source=image_data.source,
                search_query=image_data.search_query,
                tags=tags_json,
                description=image_data.description,
                photographer=image_data.photographer,
                photographer_url=image_data.photographer_url
            )
            
            self.db.add(db_image)
            self.db.commit()
            self.db.refresh(db_image)
            
            # Convert back to response model
            return self._model_to_response(db_image)
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error creating image resource: {e}")
            raise
    
    def get_image_resource(self, image_id: str) -> Optional[ImageResourceResponse]:
        """Get image resource by ID"""
        try:
            query = select(ImageResourceModel).where(ImageResourceModel.id == image_id)
            result = self.db.execute(query)
            db_image = result.scalar_one_or_none()
            
            if db_image:
                return self._model_to_response(db_image)
            return None
            
        except Exception as e:
            logger.error(f"Error getting image resource: {e}")
            raise
    
    def get_image_resource_by_url(self, url: str) -> Optional[ImageResourceResponse]:
        """Get image resource by URL"""
        try:
            query = select(ImageResourceModel).where(ImageResourceModel.url == url)
            result = self.db.execute(query)
            db_image = result.scalar_one_or_none()
            
            if db_image:
                return self._model_to_response(db_image)
            return None
            
        except Exception as e:
            logger.error(f"Error getting image resource by URL: {e}")
            raise
    
    def list_image_resources(
        self,
        page: int = 1,
        per_page: int = 20,
        search_query: Optional[str] = None,
        source: Optional[str] = None,
        download_status: Optional[str] = None,
        is_downloaded: Optional[bool] = None
    ) -> ImageResourceList:
        """List image resources with pagination and filters"""
        try:
            # Build query with filters
            query = select(ImageResourceModel)
            
            # Apply filters
            conditions = []
            if search_query:
                conditions.append(
                    or_(
                        ImageResourceModel.search_query.ilike(f"%{search_query}%"),
                        ImageResourceModel.description.ilike(f"%{search_query}%"),
                        ImageResourceModel.tags.ilike(f"%{search_query}%")
                    )
                )
            
            if source:
                conditions.append(ImageResourceModel.source == source)
            
            if download_status:
                conditions.append(ImageResourceModel.download_status == download_status)
            
            if is_downloaded is not None:
                conditions.append(ImageResourceModel.is_downloaded == is_downloaded)
            
            if conditions:
                query = query.where(and_(*conditions))
            
            # Get total count
            count_query = select(func.count()).select_from(query.subquery())
            total_result = self.db.execute(count_query)
            total = total_result.scalar()
            
            # Apply pagination
            offset = (page - 1) * per_page
            query = query.offset(offset).limit(per_page).order_by(ImageResourceModel.created_at.desc())
            
            # Execute query
            result = self.db.execute(query)
            db_images = result.scalars().all()
            
            # Convert to response models
            items = []
            for db_image in db_images:
                items.append(self._model_to_response(db_image))
            
            # Calculate pagination info
            total_pages = (total + per_page - 1) // per_page
            
            return ImageResourceList(
                items=items,
                total=total,
                page=page,
                per_page=per_page,
                total_pages=total_pages
            )
            
        except Exception as e:
            logger.error(f"Error listing image resources: {e}")
            raise
    
    def update_image_resource(self, image_id: str, update_data: ImageResourceUpdate) -> Optional[ImageResourceResponse]:
        """Update image resource"""
        try:
            # Get existing image
            query = select(ImageResourceModel).where(ImageResourceModel.id == image_id)
            result = self.db.execute(query)
            db_image = result.scalar_one_or_none()
            
            if not db_image:
                return None
            
            # Prepare update data
            update_dict = update_data.dict(exclude_unset=True)
            
            # Handle tags conversion
            if "tags" in update_dict and update_dict["tags"] is not None:
                update_dict["tags"] = json.dumps(update_dict["tags"])
            
            # Update the model
            for field, value in update_dict.items():
                setattr(db_image, field, value)
            
            db_image.updated_at = datetime.utcnow()
            
            self.db.commit()
            self.db.refresh(db_image)
            
            return self._model_to_response(db_image)
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error updating image resource: {e}")
            raise
    
    def delete_image_resource(self, image_id: str) -> bool:
        """Delete image resource"""
        try:
            query = delete(ImageResourceModel).where(ImageResourceModel.id == image_id)
            result = self.db.execute(query)
            self.db.commit()
            
            return result.rowcount > 0
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error deleting image resource: {e}")
            raise
    
    def bulk_create_image_resources(self, image_data_list: List[ImageResourceCreate]) -> List[ImageResourceResponse]:
        """Bulk create image resources"""
        try:
            db_images = []
            
            for image_data in image_data_list:
                # Convert tags list to JSON string if provided
                tags_json = None
                if image_data.tags:
                    tags_json = json.dumps(image_data.tags)
                
                # Create new image resource
                db_image = ImageResourceModel(
                    url=str(image_data.url),
                    filename=image_data.filename,
                    file_path=image_data.file_path,
                    file_size=image_data.file_size,
                    width=image_data.width,
                    height=image_data.height,
                    format=image_data.format,
                    source=image_data.source,
                    search_query=image_data.search_query,
                    tags=tags_json,
                    description=image_data.description,
                    photographer=image_data.photographer,
                    photographer_url=image_data.photographer_url
                )
                
                db_images.append(db_image)
            
            # Bulk insert
            self.db.add_all(db_images)
            self.db.commit()
            
            # Refresh all models
            for db_image in db_images:
                self.db.refresh(db_image)
            
            # Convert to response models
            return [self._model_to_response(db_image) for db_image in db_images]
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error bulk creating image resources: {e}")
            raise
    
    def update_download_status(self, image_id: str, status: str, error_message: Optional[str] = None) -> Optional[ImageResourceResponse]:
        """Update download status of image resource"""
        try:
            update_data = {
                "download_status": status,
                "updated_at": datetime.utcnow()
            }
            
            if status == "completed":
                update_data["is_downloaded"] = True
            elif status == "failed":
                update_data["error_message"] = error_message
            
            query = update(ImageResourceModel).where(ImageResourceModel.id == image_id).values(**update_data)
            result = self.db.execute(query)
            self.db.commit()
            
            if result.rowcount > 0:
                return self.get_image_resource(image_id)
            return None
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error updating download status: {e}")
            raise
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get image resource statistics"""
        try:
            # Total count
            total_query = select(func.count(ImageResourceModel.id))
            total_result = self.db.execute(total_query)
            total = total_result.scalar()
            
            # Downloaded count
            downloaded_query = select(func.count(ImageResourceModel.id)).where(ImageResourceModel.is_downloaded == True)
            downloaded_result = self.db.execute(downloaded_query)
            downloaded = downloaded_result.scalar()
            
            # Status counts
            status_query = select(
                ImageResourceModel.download_status,
                func.count(ImageResourceModel.id)
            ).group_by(ImageResourceModel.download_status)
            status_result = self.db.execute(status_query)
            status_counts = dict(status_result.all())
            
            # Source counts
            source_query = select(
                ImageResourceModel.source,
                func.count(ImageResourceModel.id)
            ).group_by(ImageResourceModel.source)
            source_result = self.db.execute(source_query)
            source_counts = dict(source_result.all())
            
            return {
                "total": total,
                "downloaded": downloaded,
                "pending": total - downloaded,
                "status_counts": status_counts,
                "source_counts": source_counts
            }
            
        except Exception as e:
            logger.error(f"Error getting statistics: {e}")
            raise
    
    def _model_to_response(self, db_image: ImageResourceModel) -> ImageResourceResponse:
        """Convert SQLAlchemy model to Pydantic response model"""
        # Parse tags JSON string back to list
        tags = None
        if db_image.tags:
            try:
                tags = json.loads(db_image.tags)
            except json.JSONDecodeError:
                tags = []
        
        return ImageResourceResponse(
            id=db_image.id,
            url=db_image.url,
            filename=db_image.filename,
            file_path=db_image.file_path,
            file_size=db_image.file_size,
            width=db_image.width,
            height=db_image.height,
            format=db_image.format,
            source=db_image.source,
            search_query=db_image.search_query,
            tags=tags,
            description=db_image.description,
            photographer=db_image.photographer,
            photographer_url=db_image.photographer_url,
            is_downloaded=db_image.is_downloaded,
            download_status=db_image.download_status,
            error_message=db_image.error_message,
            created_at=db_image.created_at,
            updated_at=db_image.updated_at
        )
