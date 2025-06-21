from sqlalchemy.orm import Session
from app.core.security import get_password_hash
from app.crud.base import CRUDBase
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate


class CRUDUser(CRUDBase[User, UserCreate, UserUpdate]):
    """
    User-specific CRUD operations.
    """
    def get_user_by_email(self, db: Session, *, email: str) -> User | None:
        """
        Fetches a user from the database by their email.

        :param db: The database session.
        :param email: The email of the user to fetch.
        :return: The user object if found, otherwise None.
        """
        return db.query(User).filter(User.email == email).first()

    def create_user(self, db: Session, *, obj_in: UserCreate) -> User:
        """
        Creates a new user in the database.

        :param db: The database session.
        :param obj_in: The user data from the API (Pydantic schema).
        :return: The newly created user object.
        """
        db_obj = User(
            email=obj_in.email,
            hashed_password=get_password_hash(obj_in.password),
            is_superuser=False,
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

# Create a singleton instance of the CRUDUser class for use in the API
user = CRUDUser(User)