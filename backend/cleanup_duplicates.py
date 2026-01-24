#!/usr/bin/env python3
"""
Quick script to cleanup duplicate characters in the database.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal
from app.models import Character, Document
import json

def cleanup_duplicates():
    db = SessionLocal()
    try:
        # Get all documents
        documents = db.query(Document).all()
        
        for doc in documents:
            print(f"\n📄 Processing document: {doc.title}")
            
            # Get all characters for this document
            characters = db.query(Character).filter(
                Character.document_id == doc.id
            ).all()
            
            print(f"Found {len(characters)} characters")
            
            # Group by name + emoji combination
            character_groups = {}
            for char in characters:
                key = (char.name.lower().strip(), char.emoji)
                if key not in character_groups:
                    character_groups[key] = []
                character_groups[key].append(char)
            
            removed_count = 0
            
            # For each group, keep the best character and delete others
            for (name, emoji), group in character_groups.items():
                if len(group) > 1:
                    print(f"  🔍 Found {len(group)} duplicates of '{name}' {emoji}")
                    
                    # Sort by: 1) most word_phrases, 2) most aliases, 3) newest
                    group.sort(key=lambda c: (
                        len(json.loads(c.word_phrases) if c.word_phrases and c.word_phrases != 'null' else []),
                        len(json.loads(c.aliases) if c.aliases else []),
                        c.created_at
                    ), reverse=True)
                    
                    # Keep the best one
                    best_character = group[0]
                    print(f"    ✅ Keeping: {best_character.id} (created: {best_character.created_at})")
                    
                    # Delete the others
                    for char in group[1:]:
                        print(f"    🗑️  Removing: {char.id} (created: {char.created_at})")
                        db.delete(char)
                        removed_count += 1
            
            print(f"✅ Removed {removed_count} duplicate characters from '{doc.title}'")
        
        # Commit all changes
        db.commit()
        print(f"\n🎉 Database cleanup complete!")
        
    except Exception as e:
        db.rollback()
        print(f"❌ Error during cleanup: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    cleanup_duplicates()