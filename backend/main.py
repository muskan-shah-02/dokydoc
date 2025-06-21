from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from app.api.endpoints import login, dashboard
from app.db.session import engine
from app.db.base_class import Base

# This function will run when the application starts up
def create_tables():
    Base.metadata.create_all(bind=engine)

# Create the main FastAPI application instance
app = FastAPI(title="Doky Project API")

# --- THIS IS THE FIX ---
# Add the CORS middleware to allow requests from your frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)
# ----------------------

@app.on_event("startup")
def on_startup():
    # This event ensures the tables are created before the app starts accepting requests.
    create_tables()

# Include the routers from the endpoint modules.
app.include_router(login.router, tags=["Login"], prefix="/api")
app.include_router(dashboard.router, tags=["Dashboard"], prefix="/api/dashboard")

@app.get("/")
def read_root():
    """
    Root endpoint for the API.
    """
    return {"message": "Welcome to the Doky Project API!"}