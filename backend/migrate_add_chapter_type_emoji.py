"""
Migration: Add type and emoji columns to chapters table
Run this script to add the new type and emoji fields to existing chapters.
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), 'plottery.db')

def migrate():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Check if columns already exist
        cursor.execute("PRAGMA table_info(chapters)")
        columns = [col[1] for col in cursor.fetchall()]
        
        # Add type column if it doesn't exist
        if 'type' not in columns:
            print("Adding 'type' column to chapters table...")
            cursor.execute("ALTER TABLE chapters ADD COLUMN type TEXT NOT NULL DEFAULT 'chapter'")
            print("✓ Added 'type' column")
        else:
            print("✓ 'type' column already exists")
        
        # Add emoji column if it doesn't exist
        if 'emoji' not in columns:
            print("Adding 'emoji' column to chapters table...")
            cursor.execute("ALTER TABLE chapters ADD COLUMN emoji TEXT")
            print("✓ Added 'emoji' column")
        else:
            print("✓ 'emoji' column already exists")
        
        conn.commit()
        print("\n✅ Migration completed successfully!")
        
    except Exception as e:
        conn.rollback()
        print(f"\n❌ Error during migration: {e}")
        raise
    finally:
        conn.close()

if __name__ == '__main__':
    print("Starting migration: Add type and emoji to chapters...")
    migrate()
