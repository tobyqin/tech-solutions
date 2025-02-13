from datetime import datetime
from typing import Optional, Dict, Any

from fastapi import HTTPException, status

from app.core.mongodb import get_database
from app.core.password import get_password_hash, verify_password
from app.models.user import User, UserCreate, UserUpdate, UserInDB, UserPasswordUpdate
from app.core.config import settings


class UserService:
    def __init__(self):
        self.db = get_database()
        self.collection = self.db.users

    async def _get_user_or_404(self, username: str) -> UserInDB:
        """Get a user by username or raise 404 if not found."""
        user = await self.get_user_by_username(username)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )
        return user

    def _is_external_user(self, user: UserInDB) -> bool:
        """Check if a user is an external user (empty hashed_password)."""
        return not user.hashed_password

    def _prepare_update_data(
        self, update_dict: Dict[str, Any], username: str
    ) -> Dict[str, Any]:
        """Prepare update data with audit fields."""
        update_data = update_dict.copy()
        update_data["updated_at"] = datetime.utcnow()
        update_data["updated_by"] = username
        return update_data

    async def _check_username_uniqueness(
        self, new_username: str, current_username: str
    ) -> None:
        """Check if a username is unique, excluding the current user."""
        if new_username != current_username:
            existing_user = await self.get_user_by_username(new_username)
            if existing_user:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Username '{new_username}' is already in use",
                )

    async def _validate_external_user_update(
        self,
        user: UserInDB,
        update_dict: Dict[str, Any],
        new_password: Optional[str] = None,
    ) -> None:
        """Validate update data for external users."""
        if self._is_external_user(user):
            allowed_fields = {"is_active", "is_superuser"}
            provided_fields = set(update_dict.keys())
            invalid_fields = provided_fields - allowed_fields
            if invalid_fields or new_password is not None:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"External users can only update is_active and is_superuser fields. Invalid fields provided: {', '.join(invalid_fields)}",
                )

    async def ensure_default_admin(self) -> None:
        """Ensure default admin user exists in the database."""
        if not all(
            [
                settings.DEFAULT_ADMIN_USERNAME,
                settings.DEFAULT_ADMIN_PASSWORD,
                settings.DEFAULT_ADMIN_EMAIL,
                settings.DEFAULT_ADMIN_FULLNAME,
            ]
        ):
            raise ValueError("Missing required default admin settings")

        admin = await self.get_user_by_username(settings.DEFAULT_ADMIN_USERNAME)
        if not admin:
            admin_user = UserCreate(
                username=settings.DEFAULT_ADMIN_USERNAME,
                email=settings.DEFAULT_ADMIN_EMAIL,
                password=settings.DEFAULT_ADMIN_PASSWORD,
                full_name=settings.DEFAULT_ADMIN_FULLNAME,
                is_active=True,
                is_superuser=True,
            )
            await self.create_user(admin_user)

    async def get_user_by_username(self, username: str) -> Optional[UserInDB]:
        """Get a user by username - internal use only."""
        user_dict = await self.collection.find_one({"username": username})
        if user_dict:
            return UserInDB(**user_dict)
        return None

    async def authenticate_user(self, username: str, password: str) -> Optional[User]:
        """Authenticate a user."""
        user = await self.get_user_by_username(username)
        if not user or not verify_password(password, user.hashed_password):
            return None
        return User.model_validate(user)

    async def get_users(
        self,
        skip: int = 0,
        limit: int = 10,
        username: Optional[str] = None,
        is_active: Optional[bool] = None,
        is_superuser: Optional[bool] = None,
    ) -> list[User]:
        """Get all users with pagination and filtering.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return
            username: Optional filter by username (case-insensitive partial match)
            is_active: Optional filter by active status
            is_superuser: Optional filter by superuser status

        Returns:
            List of matching users
        """
        # Build query
        query = {}
        if username:
            query["username"] = {"$regex": username, "$options": "i"}
        if is_active is not None:
            query["is_active"] = is_active
        if is_superuser is not None:
            query["is_superuser"] = is_superuser

        cursor = self.collection.find(query).sort("username", 1).skip(skip).limit(limit)
        users = []
        async for user_dict in cursor:
            users.append(User(**user_dict))
        return users

    async def get_user_for_api(self, username: str) -> Optional[User]:
        """Get a user by username for API response."""
        user = await self.get_user_by_username(username)
        if user:
            return User.model_validate(user)
        return None

    async def create_user(self, user: UserCreate) -> User:
        """Create a new user."""
        user.username = user.username.lower()
        await self._check_username_uniqueness(user.username, "")

        user_dict = user.model_dump(exclude={"password"})
        user_dict.update(
            {
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "hashed_password": get_password_hash(user.password)
                if user.password
                else "",
            }
        )

        result = await self.collection.insert_one(user_dict)
        user_dict["_id"] = result.inserted_id
        return User(**user_dict)

    async def update_user_password(
        self, username: str, password_update: UserPasswordUpdate, current_username: str
    ) -> bool:
        """Update a user's password."""
        username = username.lower()
        if username != current_username:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only update your own password",
            )

        user = await self._get_user_or_404(username)

        if self._is_external_user(user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="External users cannot change their password",
            )

        if not verify_password(password_update.current_password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect",
            )

        update_data = self._prepare_update_data(
            {"hashed_password": get_password_hash(password_update.new_password)},
            current_username,
        )

        result = await self.collection.update_one(
            {"username": username}, {"$set": update_data}
        )
        return result.modified_count > 0

    async def update_user_by_username(
        self, username: str, user_update: UserUpdate, current_username: str
    ) -> Optional[User]:
        """Update a user by username."""
        if username != current_username:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only update your own information",
            )

        user = await self._get_user_or_404(username)

        if self._is_external_user(user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="External users cannot update their information",
            )

        update_dict = user_update.model_dump(exclude_unset=True)
        if "username" in update_dict:
            await self._check_username_uniqueness(update_dict["username"], username)

        update_data = self._prepare_update_data(update_dict, current_username)

        result = await self.collection.find_one_and_update(
            {"username": username}, {"$set": update_data}, return_document=True
        )
        return User(**result) if result else None

    async def update_external_user(
        self, username: str, full_name: str, email: str
    ) -> Optional[User]:
        """System level update for external user information during authentication."""
        update_data = self._prepare_update_data(
            {"full_name": full_name, "email": email}, "system"
        )

        result = await self.collection.find_one_and_update(
            {"username": username}, {"$set": update_data}, return_document=True
        )
        return User(**result) if result else None

    async def admin_update_user(
        self,
        username: str,
        user_update: UserUpdate,
        admin_username: str,
        new_password: Optional[str] = None,
    ) -> Optional[User]:
        """Admin level update for user information.
        For external users, ONLY is_active and is_superuser fields can be updated."""
        user = await self._get_user_or_404(username)
        update_dict = user_update.model_dump(exclude_unset=True)

        # Validate external user updates
        await self._validate_external_user_update(user, update_dict, new_password)

        # Prepare update data based on user type
        if self._is_external_user(user):
            allowed_fields = {"is_active", "is_superuser"}
            update_dict = {k: v for k, v in update_dict.items() if k in allowed_fields}
        else:
            if new_password is not None:
                update_dict["hashed_password"] = get_password_hash(new_password)
            if "username" in update_dict:
                await self._check_username_uniqueness(update_dict["username"], username)

        update_data = self._prepare_update_data(update_dict, admin_username)

        result = await self.collection.find_one_and_update(
            {"username": username}, {"$set": update_data}, return_document=True
        )
        return User(**result) if result else None

    async def admin_delete_user(self, username: str, admin_username: str) -> bool:
        """Admin level delete for users.
        Cannot delete admin's own account or external users."""
        if username == admin_username:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Administrators cannot delete their own account",
            )

        user = await self._get_user_or_404(username)

        if self._is_external_user(user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="External users cannot be deleted, they are managed by the external auth system",
            )

        result = await self.collection.delete_one({"username": username})
        return result.deleted_count > 0

    async def count_users(
        self,
        username: Optional[str] = None,
        is_active: Optional[bool] = None,
        is_superuser: Optional[bool] = None,
    ) -> int:
        """Get total number of users matching the filter criteria.

        Args:
            username: Optional filter by username (case-insensitive partial match)
            is_active: Optional filter by active status
            is_superuser: Optional filter by superuser status

        Returns:
            Total number of matching users
        """
        query = {}
        if username:
            query["username"] = {"$regex": username, "$options": "i"}
        if is_active is not None:
            query["is_active"] = is_active
        if is_superuser is not None:
            query["is_superuser"] = is_superuser

        return await self.collection.count_documents(query)

    async def get_user_info(self, username: str) -> Optional[dict]:
        """Get basic user info (username and full_name) for display purposes."""
        user = await self.collection.find_one({"username": username}, {"full_name": 1})
        if user:
            return {"username": username, "full_name": user["full_name"]}
        return None
