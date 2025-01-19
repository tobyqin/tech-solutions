from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException, status
from app.core.auth import get_current_active_user
from app.models.tag import Tag, TagCreate, TagUpdate
from app.models.user import User
from app.services.tag_service import TagService

router = APIRouter()

@router.post("/", response_model=Tag, status_code=status.HTTP_201_CREATED)
async def create_tag(
    tag: TagCreate,
    current_user: User = Depends(get_current_active_user),
    tag_service: TagService = Depends()
) -> Any:
    """Create a new tag."""
    return await tag_service.create_tag(tag)

@router.get("/", response_model=dict)
async def get_tags(
    skip: int = 0,
    limit: int = 10,
    current_user: User = Depends(get_current_active_user),
    tag_service: TagService = Depends()
) -> Any:
    """Get all tags with pagination."""
    tags = await tag_service.get_tags(skip=skip, limit=limit)
    total = await tag_service.count_tags()
    return {
        "items": tags,
        "total": total,
        "skip": skip,
        "limit": limit
    }

@router.get("/{tag_id}", response_model=Tag)
async def get_tag(
    tag_id: str,
    current_user: User = Depends(get_current_active_user),
    tag_service: TagService = Depends()
) -> Any:
    """Get a specific tag."""
    tag = await tag_service.get_tag(tag_id)
    if not tag:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tag not found"
        )
    return tag

@router.put("/{tag_id}", response_model=Tag)
async def update_tag(
    tag_id: str,
    tag_update: TagUpdate,
    current_user: User = Depends(get_current_active_user),
    tag_service: TagService = Depends()
) -> Any:
    """Update a tag."""
    tag = await tag_service.update_tag(tag_id, tag_update)
    if not tag:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tag not found"
        )
    return tag

@router.delete("/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tag(
    tag_id: str,
    current_user: User = Depends(get_current_active_user),
    tag_service: TagService = Depends()
) -> None:
    """Delete a tag."""
    success = await tag_service.delete_tag(tag_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tag not found"
        )

@router.get("/solution/{solution_id}", response_model=TagList)
async def get_solution_tags(
    solution_id: str,
    tag_service: TagService = Depends()
):
    """Get all tags for a specific solution"""
    return await tag_service.get_solution_tags(solution_id)

@router.post("/solution/{solution_id}/tags/{tag_id}")
async def add_solution_tag(
    solution_id: str,
    tag_id: str,
    current_user: dict = Depends(get_current_user),
    tag_service: TagService = Depends()
):
    """Add a tag to a solution"""
    try:
        success = await tag_service.add_solution_tag(solution_id, tag_id)
        if not success:
            raise HTTPException(status_code=404, detail="Solution or tag not found")
        return {"status": "success", "message": "Tag added to solution successfully"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/solution/{solution_id}/tags/{tag_id}")
async def remove_solution_tag(
    solution_id: str,
    tag_id: str,
    current_user: dict = Depends(get_current_user),
    tag_service: TagService = Depends()
):
    """Remove a tag from a solution"""
    success = await tag_service.remove_solution_tag(solution_id, tag_id)
    if not success:
        raise HTTPException(status_code=404, detail="Solution or tag not found")
    return {"status": "success", "message": "Tag removed from solution successfully"}
