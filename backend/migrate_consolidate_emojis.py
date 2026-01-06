"""
Database migration to consolidate emoji system.

This migration:
1. Removes deprecated tables: emoji_tags, word_emoji_mappings, custom_emoji_sets, character_definitions
2. Adds new unified 'characters' table
3. Updates 'sentences' table to store character_refs instead of emoji relationships
4. Migrates existing data where possible
"""

import sqlite3
import json
from datetime import datetime, timezone

DB_PATH = "plottery.db"


def migrate():
    """Execute the database migration."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("🔄 Starting emoji system consolidation migration...")
    
    try:
        # Step 1: Create new characters table
        print("📋 Creating new 'characters' table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS characters (
                id TEXT PRIMARY KEY,
                document_id TEXT NOT NULL,
                name TEXT NOT NULL,
                emoji TEXT NOT NULL,
                color TEXT NOT NULL,
                aliases TEXT,
                description TEXT,
                created_at TIMESTAMP NOT NULL,
                FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
            )
        """)
        
        # Step 2: Migrate character_definitions to characters (if exists)
        print("📦 Migrating existing character definitions...")
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='character_definitions'
        """)
        
        if cursor.fetchone():
            # Copy data from character_definitions to characters
            cursor.execute("""
                INSERT INTO characters (id, document_id, name, emoji, color, aliases, description, created_at)
                SELECT 
                    id,
                    document_id,
                    name,
                    emoji,
                    COALESCE(color, '#6366F1') as color,
                    aliases,
                    description,
                    created_at
                FROM character_definitions
            """)
            migrated_count = cursor.rowcount
            print(f"  ✅ Migrated {migrated_count} character definitions")
        
        # Step 3: Add character_refs column to sentences
        print("📋 Adding character_refs column to sentences...")
        try:
            cursor.execute("""
                ALTER TABLE sentences ADD COLUMN character_refs TEXT
            """)
            print("  ✅ Column added")
        except sqlite3.OperationalError as e:
            if "duplicate column" in str(e).lower():
                print("  ℹ️  Column already exists")
            else:
                raise
        
        # Step 4: Initialize character_refs to empty JSON array
        cursor.execute("""
            UPDATE sentences 
            SET character_refs = '[]' 
            WHERE character_refs IS NULL
        """)
        
        # Step 5: Drop deprecated tables
        print("🗑️  Removing deprecated tables...")
        deprecated_tables = [
            'emoji_tags',
            'word_emoji_mappings', 
            'custom_emoji_sets',
            'character_definitions'
        ]
        
        for table in deprecated_tables:
            cursor.execute(f"""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='{table}'
            """)
            if cursor.fetchone():
                cursor.execute(f"DROP TABLE {table}")
                print(f"  ✅ Dropped {table}")
        
        # Commit all changes
        conn.commit()
        print("\n✨ Migration completed successfully!")
        print("\n📊 New schema:")
        print("  • sentences: now stores character_refs (JSON array of character IDs)")
        print("  • characters: SINGLE SOURCE OF TRUTH for all emoji rendering")
        print("  • Removed: emoji_tags, word_emoji_mappings, custom_emoji_sets")
        
    except Exception as e:
        conn.rollback()
        print(f"\n❌ Migration failed: {e}")
        raise
    
    finally:
        conn.close()


if __name__ == "__main__":
    migrate()
