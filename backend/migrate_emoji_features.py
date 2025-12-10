"""
Database migration script to add enhanced emoji features.
Run this to create the new tables for word mappings, custom emoji sets, and character definitions.
"""

from app.database import engine, Base
from app.models import WordEmojiMapping, CustomEmojiSet, CharacterDefinition

def migrate():
    """Create new tables for enhanced emoji features."""
    print("Creating new tables for enhanced emoji features...")
    
    # This will create only the new tables that don't exist yet
    Base.metadata.create_all(bind=engine)
    
    print("✓ Migration complete!")
    print("New tables created:")
    print("  - word_emoji_mappings")
    print("  - custom_emoji_sets")
    print("  - character_definitions")

if __name__ == "__main__":
    migrate()
