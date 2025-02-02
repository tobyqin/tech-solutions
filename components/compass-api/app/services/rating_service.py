from typing import List, Optional, Tuple, Dict
from datetime import datetime
from bson import ObjectId
from pymongo import DESCENDING, ASCENDING
from fastapi import HTTPException, status

from app.core.database import get_database
from app.models.rating import RatingCreate, RatingInDB, Rating

VALID_SORT_FIELDS = {'created_at', 'updated_at', 'score'}

class RatingService:
    def __init__(self):
        self.db = get_database()

    async def _convert_to_rating(self, rating_data: dict) -> Rating:
        """Private helper method to convert rating data to Rating model with full name"""
        # Get user's full name from users collection
        user = await self.db.users.find_one({"username": rating_data["username"]}, {"full_name": 1})
        if user:
            rating_data["full_name"] = user["full_name"]
        return Rating(**rating_data)

    async def get_ratings(
        self,
        skip: int = 0,
        limit: int = 20,
        sort: str = "-created_at"  # Default sort by created_at desc
    ) -> Tuple[List[Rating], int]:
        """Get all ratings with pagination and sorting.
        Default sort is by created_at in descending order (newest first)."""
        
        # Parse sort parameter
        sort_field = "created_at"
        sort_direction = DESCENDING  # Default to descending

        if sort.startswith("-"):
            sort_field = sort[1:]  # Remove the minus sign
            sort_direction = DESCENDING
        else:
            sort_field = sort
            sort_direction = ASCENDING

        # Validate sort field
        if sort_field not in VALID_SORT_FIELDS:
            raise ValueError(f"Invalid sort field: {sort_field}. Valid fields are: {', '.join(VALID_SORT_FIELDS)}")

        # Execute query with sort
        cursor = self.db.ratings.find().sort(sort_field, sort_direction).skip(skip).limit(limit)
        ratings = [await self._convert_to_rating(rating) async for rating in cursor]
        total = await self.db.ratings.count_documents({})
        
        return ratings, total

    async def get_solution_ratings(self, solution_slug: str, skip: int, limit: int, sort_by: str) -> Tuple[List[Rating], int]:
        query = {"solution_slug": solution_slug}
        sort_field = "created_at" if sort_by == "created_at" else "score"
        cursor = self.db.ratings.find(query).sort(sort_field, DESCENDING).skip(skip).limit(limit)
        ratings = [await self._convert_to_rating(rating) async for rating in cursor]
        total = await self.db.ratings.count_documents(query)
        return ratings, total

    async def get_user_rating(self, solution_slug: str, username: str) -> Optional[Rating]:
        rating = await self.db.ratings.find_one({"solution_slug": solution_slug, "username": username})
        if rating:
            return await self._convert_to_rating(rating)
        return None

    async def get_rating_summary(self, solution_slug: str) -> Dict:
        """Get rating summary statistics for a solution"""
        pipeline = [
            {"$match": {"solution_slug": solution_slug}},
            {
                "$group": {
                    "_id": None,
                    "average": {"$avg": "$score"},
                    "count": {"$sum": 1},
                    "scores": {"$push": "$score"}
                }
            }
        ]
        
        result = await self.db.ratings.aggregate(pipeline).to_list(1)
        if not result:
            return {
                "average": 0,
                "count": 0,
                "distribution": {str(i): 0 for i in range(1, 6)}
            }
            
        summary = result[0]
        # Calculate distribution
        distribution = {str(i): 0 for i in range(1, 6)}
        for score in summary["scores"]:
            distribution[str(score)] += 1
            
        return {
            "average": round(summary["average"], 2),
            "count": summary["count"],
            "distribution": distribution
        }

    async def create_or_update_rating(self, solution_slug: str, rating: RatingCreate, username: str) -> RatingInDB:
        # First check if solution exists
        solution = await self.db.solutions.find_one({"slug": solution_slug})
        if not solution:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Solution with slug '{solution_slug}' not found"
            )

        now = datetime.utcnow()
        rating_data = rating.model_dump()
        
        # Try to update existing rating first
        result = await self.db.ratings.update_one(
            {"solution_slug": solution_slug, "username": username},
            {
                "$set": {
                    "score": rating_data["score"],
                    "comment": rating_data.get("comment"),
                    "updated_at": now
                }
            }
        )
        
        # If no existing rating was updated, create a new one
        if result.modified_count == 0:
            new_rating = {
                "solution_slug": solution_slug,
                "username": username,
                "score": rating_data["score"],
                "comment": rating_data.get("comment"),
                "created_at": now,
                "updated_at": now
            }
            await self.db.ratings.insert_one(new_rating)
            return RatingInDB(**new_rating)
        
        # Return the updated rating
        return await self.get_user_rating(solution_slug, username)