"""
Migration: Add emojis column to sentences table

Adds support for hybrid emoji system:
- emojis: Raw emoji strings (free generation)
- character_refs: Character IDs (structured generation)
"""
import sqlite3
import json

DB_PATH = "plottery.db"

def migrate():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("🔄 Adding emojis column to sentences table...")
    
    try:
        # Add emojis column
        cursor.execute("""
            ALTER TABLE sentences 
            ADD COLUMN emojis TEXT
        """)
        
        print("✅ Added emojis column")
        
        # Initialize emojis to empty array for existing sentences
        cursor.execute("""
            UPDATE sentences 
            SET emojis = '[]' 
            WHERE emojis IS NULL
        """)
        
        rows_updated = cursor.rowcount
        print(f"✅ Initialized emojis for {rows_updated} existing sentences")
        
        conn.commit()
        print("\n✨ Migration complete!")
        
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            print("⚠️  Column 'emojis' already exists, skipping...")
        else:
            raise
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
