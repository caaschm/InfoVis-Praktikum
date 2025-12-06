"""Main FastAPI application."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timezone
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from app.database import init_db
from app.routers import documents, sentences, ai
from app.routers import chapters
from app.schemas import HealthResponse

# Create FastAPI app
app = FastAPI(
    title="Plottery API",
    description="Creative writing app with AI-powered emoji and text generation",
    version="1.0.0"
)

# Configure CORS to allow Angular dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:4200",  # Angular dev server
        "http://127.0.0.1:4200",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(documents.router)
app.include_router(sentences.router)
app.include_router(ai.router)
app.include_router(chapters.router)


@app.on_event("startup")
def on_startup():
    """Initialize database on startup."""
    init_db()


@app.get("/", tags=["root"])
def read_root():
    """Root endpoint."""
    return {
        "message": "Welcome to Plottery API",
        "docs": "/docs",
        "health": "/health"
    }


@app.get("/health", response_model=HealthResponse, tags=["health"])
def health_check():
    """Health check endpoint for monitoring and testing."""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now(timezone.utc)
    )
