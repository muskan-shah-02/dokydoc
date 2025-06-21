from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from app.api.endpoints import login
from app.db.session import engine
from app.db.base_class import Base

# This function will run when the application starts up
def create_tables():
    Base.metadata.create_all(bind=engine)

# Create the main FastAPI application instance
app = FastAPI(title="Doky Project API")

# Set all CORS enabled origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    # This event ensures the tables are created before the app starts accepting requests.
    create_tables()

# Include the router from the login endpoints module.
app.include_router(login.router, tags=["Users"], prefix="/api")

@app.get("/")
def read_root():
    """
    Root endpoint for the API.
    """
    return {"message": "Welcome to the Doky Project API!"}