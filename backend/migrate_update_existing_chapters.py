"""
Migration: Update existing chapters to have default type
Run this script to set default 'chapter' type for existing chapters that might have NULL type.
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), 'plottery.db')

def migrate():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Update all chapters that have NULL or empty type to 'chapter'
        cursor.execute("""
            UPDATE chapters 
            SET type = 'chapter' 
            WHERE type IS NULL OR type = ''
        """)
        
        updated_count = cursor.rowcount
        print(f"✓ Updated {updated_count} chapters with default type 'chapter'")
        
        conn.commit()
        print("\n✅ Migration completed successfully!")
        
    except Exception as e:
        conn.rollback()
        print(f"\n❌ Error during migration: {e}")
        raise
    finally:
        conn.close()

if __name__ == '__main__':
    print("Starting migration: Update existing chapters with default type...")
    migrate()
