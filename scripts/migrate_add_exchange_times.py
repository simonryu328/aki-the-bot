#!/usr/bin/env python3
"""
Migration script to add exchange_start and exchange_end columns to diary_entries table.

Usage:
    uv run python scripts/migrate_add_exchange_times.py
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from memory.database import db

def migrate():
    """Add exchange_start and exchange_end columns to diary_entries table."""
    print("Adding exchange_start and exchange_end columns to diary_entries table...")
    
    with db.get_session() as session:
        # Check if columns already exist
        result = session.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='diary_entries' 
            AND column_name IN ('exchange_start', 'exchange_end')
        """))
        existing_columns = [row[0] for row in result]
        
        if 'exchange_start' in existing_columns and 'exchange_end' in existing_columns:
            print("✓ Columns already exist. No migration needed.")
            return
        
        # Add exchange_start column if it doesn't exist
        if 'exchange_start' not in existing_columns:
            print("Adding exchange_start column...")
            session.execute(text("""
                ALTER TABLE diary_entries 
                ADD COLUMN exchange_start TIMESTAMP NULL
            """))
            session.execute(text("""
                CREATE INDEX IF NOT EXISTS ix_diary_entries_exchange_start 
                ON diary_entries(exchange_start)
            """))
            print("✓ Added exchange_start column with index")
        
        # Add exchange_end column if it doesn't exist
        if 'exchange_end' not in existing_columns:
            print("Adding exchange_end column...")
            session.execute(text("""
                ALTER TABLE diary_entries 
                ADD COLUMN exchange_end TIMESTAMP NULL
            """))
            session.execute(text("""
                CREATE INDEX IF NOT EXISTS ix_diary_entries_exchange_end 
                ON diary_entries(exchange_end)
            """))
            print("✓ Added exchange_end column with index")
        
        session.commit()
        print("\n✅ Migration completed successfully!")
        print("\nThese columns will be populated for new compact_summary entries.")
        print("Existing entries will have NULL values for these fields.")

if __name__ == "__main__":
    try:
        migrate()
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        sys.exit(1)

# Made with Bob
