from fastapi import APIRouter, HTTPException, Depends
from src.models.item import ItemCreate, ItemResponse
from src.config.settings import settings
from src.utils.env_utils import get_environment_info, validate_required_env_vars
from typing import List, Dict, Any

router = APIRouter()
# In-memory storage (use database in production)
items_db = []

@router.get("/items/", response_model=List[ItemResponse])
def get_items():
    """Get all items with environment-aware behavior"""
    # Example of using environment variables in routes
    if settings.is_production:
        # In production, you might want to add caching or rate limiting
        pass
    
    if settings.debug:
        # In debug mode, you might want to add extra logging
        print(f"Debug: Retrieved {len(items_db)} items")
    
    return items_db

@router.get("/items/{item_id}", response_model=ItemResponse)
def get_item(item_id: int):
    if item_id < 0 or item_id >= len(items_db):
        raise HTTPException(status_code=404, detail="Item not found")
    
    # Example of environment-specific error handling
    if settings.is_development:
        # In development, provide more detailed error information
        print(f"Development: Accessing item with ID {item_id}")
    
    return items_db[item_id]

@router.post("/items/", response_model=ItemResponse)
def create_item(item: ItemCreate):
    # Example of using environment variables for validation
    if settings.is_production and not settings.external_api_key:
        raise HTTPException(
            status_code=500, 
            detail="External API key not configured for production"
        )
    
    total_price = item.price + (item.tax or 0)
    new_item = ItemResponse(
        id=len(items_db),
        name=item.name,
        description=item.description,
        price=item.price,
        tax=item.tax,
        total_price=total_price
    )
    items_db.append(new_item)
    
    # Environment-specific logging
    if settings.debug:
        print(f"Debug: Created item with ID {new_item.id}")
    
    return new_item

@router.put("/items/{item_id}", response_model=ItemResponse)
def update_item(item_id: int, item: ItemCreate):
    if item_id < 0 or item_id >= len(items_db):
        raise HTTPException(status_code=404, detail="Item not found")
    
    total_price = item.price + (item.tax or 0)
    updated_item = ItemResponse(
        id=item_id,
        name=item.name,
        description=item.description,
        price=item.price,
        tax=item.tax,
        total_price=total_price
    )
    items_db[item_id] = updated_item
    return updated_item

@router.delete("/items/{item_id}")
def delete_item(item_id: int):
    if item_id < 0 or item_id >= len(items_db):
        raise HTTPException(status_code=404, detail="Item not found")
    
    deleted_item = items_db.pop(item_id)
    return {"message": "Item deleted", "item": deleted_item}

@router.get("/items/env/info")
def get_environment_info_route():
    """Get environment information for debugging"""
    if not settings.debug:
        raise HTTPException(status_code=403, detail="Environment info only available in debug mode")
    
    return {
        "environment_info": get_environment_info(),
        "required_vars_status": validate_required_env_vars(),
        "app_config": {
            "app_name": settings.app_name,
            "version": settings.version,
            "api_prefix": settings.api_prefix
        }
    }

@router.get("/items/config/validation")
def validate_configuration():
    """Validate that all required environment variables are set"""
    validation_results = validate_required_env_vars()
    all_valid = all(validation_results.values())
    
    return {
        "configuration_valid": all_valid,
        "validation_results": validation_results,
        "missing_vars": [var for var, valid in validation_results.items() if not valid]
    }