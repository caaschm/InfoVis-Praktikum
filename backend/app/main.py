"""Main FastAPI application."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timezone
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from app.database import init_db
from app.routers import documents, sentences, ai, characters, chapters
from app.schemas import HealthResponse

# Create FastAPI app
app = FastAPI(
    title="Plottery API",
    description="Creative writing app with character-based emoji visualization",
    version="2.0.0"  # Major version bump - consolidated emoji system
)

# Configure CORS to allow Angular dev server
from fastapi.middleware.cors import CORSMiddleware
import os

origins = [
    "http://localhost:4200",
    "https://plottery.netlify.app",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

""" # Configure CORS to allow Angular dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
@@ -28,7 +45,7 @@
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
)"""

# Include routers
app.include_router(documents.router)
app.include_router(sentences.router)
app.include_router(ai.router)
app.include_router(characters.router)
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
