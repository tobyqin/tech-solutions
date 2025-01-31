from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response

from app.core.auth import get_current_active_user
from app.models.category import Category, CategoryCreate, CategoryUpdate, CategoryInDB
from app.models.user import User
from app.models.response import StandardResponse
from app.services.category_service import CategoryService

router = APIRouter()

@router.post("/", response_model=StandardResponse[Category], status_code=status.HTTP_201_CREATED)
async def create_category(
    category: CategoryCreate,
    current_user: User = Depends(get_current_active_user),
    category_service: CategoryService = Depends()
) -> StandardResponse[Category]:
    """Create a new category."""
    try:
        result = await category_service.create_category(category, current_user.username)
        category_with_usage = await category_service.get_category_with_usage(result)
        return StandardResponse.of(category_with_usage)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/", response_model=StandardResponse[List[Category]])
async def get_categories(
    skip: int = 0,
    limit: int = 100,
    category_service: CategoryService = Depends()
) -> StandardResponse[List[Category]]:
    """Get all categories with pagination. Default limit is 100 items."""
    categories = await category_service.get_categories(skip=skip, limit=limit)
    total = await category_service.count_categories()
    
    # Convert to Category model with usage count
    categories_with_usage = []
    for category in categories:
        category_with_usage = await category_service.get_category_with_usage(category)
        categories_with_usage.append(category_with_usage)
    
    return StandardResponse.paginated(
        data=categories_with_usage,
        total=total,
        skip=skip,
        limit=limit
    )

@router.get("/{name}", response_model=StandardResponse[Category])
async def get_category(
    name: str,
    category_service: CategoryService = Depends()
) -> StandardResponse[Category]:
    """Get a specific category by name."""
    category = await category_service.get_category_by_name(name)
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found"
        )
    category_with_usage = await category_service.get_category_with_usage(category)
    return StandardResponse.of(category_with_usage)

@router.put("/{name}", response_model=StandardResponse[Category])
async def update_category(
    name: str,
    category_update: CategoryUpdate,
    current_user: User = Depends(get_current_active_user),
    category_service: CategoryService = Depends()
) -> StandardResponse[Category]:
    """Update a category by name."""
    try:
        category = await category_service.update_category_by_name(name, category_update, current_user.username)
        if not category:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Category not found"
            )
        category_with_usage = await category_service.get_category_with_usage(category)
        return StandardResponse.of(category_with_usage)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/{name}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def delete_category(
    name: str,
    current_user: User = Depends(get_current_active_user),
    category_service: CategoryService = Depends()
) -> None:
    """Delete a category by name. Will return 400 error if category is being used by any solutions."""
    try:
        success = await category_service.delete_category_by_name(name)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Category not found"
            )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
