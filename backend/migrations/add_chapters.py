# Run this migration script to add chapters support
from app.database import engine, Base
from app import models

# This will create the chapters table
Base.metadata.create_all(bind=engine)
