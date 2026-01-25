import asyncio
from app.db.session import get_db_context
from app.crud.crud_user import user as user_crud
from app.crud.crud_tenant import tenant as tenant_crud
from app.schemas.user import UserCreate, Role
from app.schemas.tenant import TenantCreate
from app.core.logging import get_logger

# Get logger for this module
logger = get_logger("initial_data")

# SPRINT 2 Phase 8: Updated to handle tenant_id requirement

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
        # SPRINT 2 Phase 8: Create or get default tenant first
        default_tenant = tenant_crud.get_by_subdomain(db, subdomain="default")

        if not default_tenant:
            logger.info("Creating default tenant...")
            tenant_in = TenantCreate(
                name="Default Organization",
                subdomain="default",
                tier="pro",  # Give default tenant pro tier
                billing_type="prepaid"
            )
            default_tenant = tenant_crud.create_tenant(db, obj_in=tenant_in)
            logger.info(f"Created default tenant: {default_tenant.name} (ID: {default_tenant.id})")
        else:
            logger.info(f"Using existing default tenant (ID: {default_tenant.id})")

        # Create users in the default tenant
        for user_data in users_to_create:
            user = user_crud.get_user_by_email(db, email=user_data["email"])

            # If user doesn't exist, create them
            if not user:
                user_in_create = UserCreate(
                    email=user_data["email"],
                    password=user_data["password"],
                    roles=user_data["roles"],
                )
                # SPRINT 2 Phase 8: Pass tenant_id when creating user
                user = user_crud.create_user(
                    db,
                    obj_in=user_in_create,
                    tenant_id=default_tenant.id
                )
                logger.info(f"Created user: {user.email} in tenant {default_tenant.id}")

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