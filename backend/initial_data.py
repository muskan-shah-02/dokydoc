import asyncio
from app.db.session import get_db_context
from app.crud.crud_user import user as user_crud
from app.schemas.user import UserCreate, Role
from app.core.logging import get_logger

# Get logger for this module
logger = get_logger("initial_data")

# The user data remains the same
users_to_create = [
    {
        "email": "superuser@example.com",
        "password": "superuserpassword",
        "roles": [Role.CXO, Role.BA, Role.DEVELOPER, Role.PRODUCT_MANAGER],
    },
    {
        "email": "cxo@example.com",
        "password": "cxopassword",
        "roles": [Role.CXO],
    },
    {
        "email": "ba@example.com",
        "password": "bapassword",
        "roles": [Role.BA],
    },
    {
        "email": "dev@example.com",
        "password": "devpassword",
        "roles": [Role.DEVELOPER],
    },
    {
        "email": "pm@example.com",
        "password": "pmpassword",
        "roles": [Role.PRODUCT_MANAGER],
    },
]


async def main() -> None:
    logger.info("Starting initial data creation process...")
    
    with get_db_context() as db:
        for user_data in users_to_create:
            user = user_crud.get_user_by_email(db, email=user_data["email"])
            
            # If user doesn't exist, create them
            if not user:
                user_in_create = UserCreate(
                    email=user_data["email"],
                    password=user_data["password"],
                    roles=user_data["roles"],
                )
                user = user_crud.create_user(db, obj_in=user_in_create)
                logger.info(f"Created user: {user.email}")

            # --- EXPLICITLY SET AND SAVE ROLES ---
            # This part ensures the roles are correct, even if they were not set on creation
            role_values = [role.value for role in user_data["roles"]]
            if user.roles != role_values:
                logger.info(f"Updating roles for {user.email}...")
                user.roles = role_values
                db.add(user)
                db.commit()
                db.refresh(user)
                logger.info(f"Successfully set roles for {user.email} to: {user.roles}")
            else:
                 logger.info(f"Roles for {user.email} are already correct.")

    logger.info("Initial data creation process finished.")


if __name__ == "__main__":
    asyncio.run(main())