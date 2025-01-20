from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.auth import get_current_active_user
from app.models.user import User
from app.services.rating_service import RatingService
from app.models.rating import RatingCreate

router = APIRouter()

@router.get("/solution/{solution_slug}", response_model=dict, tags=["ratings"])
async def get_solution_ratings(
    solution_slug: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort_by: str = Query("created_at", regex="^(created_at|score)$"),
):
    """
    Get all ratings for a solution with pagination and sorting.
    
    - **solution_slug**: Unique identifier of the solution
    - **page**: Page number for pagination
    - **page_size**: Number of ratings per page
    - **sort_by**: Field to sort by (created_at or score)
    """
    rating_service = RatingService()
    skip = (page - 1) * page_size
    ratings, total = await rating_service.get_solution_ratings(
        solution_slug=solution_slug,
        skip=skip,
        limit=page_size,
        sort_by=sort_by
    )
    return {
        "status": "success",
        "data": ratings,
        "meta": {
            "page": page,
            "page_size": page_size,
            "total": total
        }
    }

@router.get("/solution/{solution_slug}/me", response_model=dict, tags=["ratings"])
async def get_user_rating(
    solution_slug: str,
    current_user: User = Depends(get_current_active_user)
):
    """
    Get the current user's rating for a solution.
    
    - **solution_slug**: Unique identifier of the solution
    """
    rating_service = RatingService()
    rating = await rating_service.get_user_rating(solution_slug, current_user.username)
    if not rating:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rating not found"
        )
    return {
        "status": "success",
        "data": rating
    }

@router.post("/solution/{solution_slug}", response_model=dict, status_code=status.HTTP_201_CREATED, tags=["ratings"])
async def create_or_update_rating(
    solution_slug: str,
    rating: RatingCreate,
    current_user: User = Depends(get_current_active_user)
):
    """
    Create or update a rating for a solution.
    
    - **solution_slug**: Unique identifier of the solution
    - **rating**: Rating details including score and optional comment
    """
    rating_service = RatingService()
    try:
        updated_rating = await rating_service.create_or_update_rating(
            solution_slug=solution_slug,
            rating=rating,
            username=current_user.username
        )
        return {
            "status": "success",
            "data": updated_rating
        }
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating/updating rating: {str(e)}"
        )

@router.get("/solution/{solution_slug}/summary", response_model=dict, tags=["ratings"])
async def get_solution_rating_summary(
    solution_slug: str,
):
    """
    Get rating summary statistics for a solution.
    
    Returns:
    - average: Average rating score
    - count: Total number of ratings
    - distribution: Count of ratings for each score (1-5)
    """
    rating_service = RatingService()
    summary = await rating_service.get_rating_summary(solution_slug)
    return {
        "status": "success",
        "data": summary
    } 