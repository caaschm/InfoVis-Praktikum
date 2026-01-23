import sqlite3
import os

DB_PATH = "plottery.db"

def add_column():
    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Check if column exists
        cursor.execute("PRAGMA table_info(sentences)")
        columns = [info[1] for info in cursor.fetchall()]
        
        if "is_ai_generated" in columns:
            print("Column 'is_ai_generated' already exists.")
        else:
            print("Adding 'is_ai_generated' column...")
            cursor.execute("ALTER TABLE sentences ADD COLUMN is_ai_generated BOOLEAN DEFAULT 0")
            conn.commit()
            print("Column added successfully.")
            
        if "ai_category" in columns:
             print("Column 'ai_category' already exists.")
        else:
             print("Adding 'ai_category' column...")
             cursor.execute("ALTER TABLE sentences ADD COLUMN ai_category TEXT")
             conn.commit()
             print("Column ai_category added successfully.")
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    add_column()
