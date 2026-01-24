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
    
    # Create chapters table (only if it doesn't exist)
    Base.metadata.create_all(bind=engine)
    
    with engine.connect() as conn:
        # Check and fix chapters table columns
        print("Checking chapters table structure...")
        result = conn.execute(text("PRAGMA table_info(chapters)"))
        chapter_columns = [row[1] for row in result]
        
        # Add missing columns to chapters table
        if 'type' not in chapter_columns:
            print("Adding 'type' column to chapters table...")
            try:
                conn.execute(text("ALTER TABLE chapters ADD COLUMN type VARCHAR NOT NULL DEFAULT 'chapter'"))
                print("✓ Added 'type' column")
            except Exception as e:
                print(f"Note: Could not add type column: {e}")
        else:
            print("✓ 'type' column already exists in chapters table")
            
        if 'emoji' not in chapter_columns:
            print("Adding 'emoji' column to chapters table...")
            try:
                conn.execute(text("ALTER TABLE chapters ADD COLUMN emoji VARCHAR"))
                print("✓ Added 'emoji' column")
            except Exception as e:
                print(f"Note: Could not add emoji column: {e}")
        else:
            print("✓ 'emoji' column already exists in chapters table")
        
        # Check if sentences table has chapter_id column
        result = conn.execute(text("PRAGMA table_info(sentences)"))
        sentence_columns = [row[1] for row in result]
        
        if 'chapter_id' not in sentence_columns:
            print("Adding chapter_id column to sentences table...")
            try:
                conn.execute(text("ALTER TABLE sentences ADD COLUMN chapter_id VARCHAR"))
                print("✓ Added chapter_id column to sentences table")
            except Exception as e:
                print(f"Note: Could not add chapter_id column (may already exist): {e}")
        else:
            print("✓ chapter_id column already exists in sentences table")
            
        # Clean up orphaned chapters (optional but recommended)
        print("Checking for orphaned chapters...")
        result = conn.execute(text("SELECT COUNT(*) FROM chapters WHERE document_id NOT IN (SELECT id FROM documents)"))
        orphaned_count = result.fetchone()[0]
        
        if orphaned_count > 0:
            print(f"Found {orphaned_count} orphaned chapters. Cleaning up...")
            conn.execute(text("DELETE FROM chapters WHERE document_id NOT IN (SELECT id FROM documents)"))
            print(f"✓ Removed {orphaned_count} orphaned chapters")
        else:
            print("✓ No orphaned chapters found")
            
        conn.commit()
    
    print("✓ Migration complete!")
    print("Tables/columns verified:")
    print("  - chapters table (with type and emoji columns)")
    print("  - chapter_id column in sentences table")
    print("  - orphaned chapters cleaned up")

if __name__ == "__main__":
    migrate()
