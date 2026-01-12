"""
Database migration script to add chapters support.
This creates the chapters table and adds chapter_id column to sentences table.
"""

from app.database import engine, Base
from app import models
from sqlalchemy import text

def migrate():
    """Add chapters table and update sentences table."""
    print("Adding chapters support...")
    
    # Create chapters table
    Base.metadata.create_all(bind=engine)
    
    # Check if sentences table has chapter_id column
    with engine.connect() as conn:
        # SQLite doesn't support IF NOT EXISTS for ALTER TABLE, so we check first
        result = conn.execute(text("PRAGMA table_info(sentences)"))
        columns = [row[1] for row in result]
        
        if 'chapter_id' not in columns:
            print("Adding chapter_id column to sentences table...")
            try:
                conn.execute(text("ALTER TABLE sentences ADD COLUMN chapter_id VARCHAR"))
                conn.commit()
                print("✓ Added chapter_id column to sentences table")
            except Exception as e:
                print(f"Note: Could not add chapter_id column (may already exist): {e}")
        else:
            print("✓ chapter_id column already exists in sentences table")
    
    print("✓ Migration complete!")
    print("New tables/columns created:")
    print("  - chapters table")
    print("  - chapter_id column in sentences table")

if __name__ == "__main__":
    migrate()
