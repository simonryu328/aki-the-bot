#!/usr/bin/env python3
"""
Migration script to add timezone and location fields to users table.

Adds:
- timezone (String, default 'America/Toronto')
- location_latitude (Float, nullable)
- location_longitude (Float, nullable)
- location_name (String, nullable)
"""

import sys
import os

# Add parent directory to path so we can import config
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from config.settings import settings

def migrate():
    """Add timezone and location fields to users table."""
    print("Adding timezone and location fields to users table...")
    
    engine = create_engine(settings.DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        # Check which columns already exist
        existing_columns = session.execute(text("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name='users'
            AND column_name IN ('timezone', 'location_latitude', 'location_longitude', 'location_name')
        """))
        existing_columns = [row[0] for row in existing_columns]
        
        if all(col in existing_columns for col in ['timezone', 'location_latitude', 'location_longitude', 'location_name']):
            print("✓ All columns already exist. No migration needed.")
            return
        
        # Add timezone column if it doesn't exist
        if 'timezone' not in existing_columns:
            print("Adding timezone column...")
            session.execute(text("""
                ALTER TABLE users
                ADD COLUMN timezone VARCHAR(100) DEFAULT 'America/Toronto' NOT NULL
            """))
            print("✓ Added timezone column")
        
        # Add location_latitude column if it doesn't exist
        if 'location_latitude' not in existing_columns:
            print("Adding location_latitude column...")
            session.execute(text("""
                ALTER TABLE users
                ADD COLUMN location_latitude FLOAT NULL
            """))
            print("✓ Added location_latitude column")
        
        # Add location_longitude column if it doesn't exist
        if 'location_longitude' not in existing_columns:
            print("Adding location_longitude column...")
            session.execute(text("""
                ALTER TABLE users
                ADD COLUMN location_longitude FLOAT NULL
            """))
            print("✓ Added location_longitude column")
        
        # Add location_name column if it doesn't exist
        if 'location_name' not in existing_columns:
            print("Adding location_name column...")
            session.execute(text("""
                ALTER TABLE users
                ADD COLUMN location_name VARCHAR(255) NULL
            """))
            print("✓ Added location_name column")
        
        session.commit()
        print("\n✅ Migration completed successfully!")
        print("\nNew fields added:")
        print("  - timezone: User's IANA timezone (default: America/Toronto)")
        print("  - location_latitude: Latitude coordinate")
        print("  - location_longitude: Longitude coordinate")
        print("  - location_name: Human-readable location name")
        
    except Exception as e:
        session.rollback()
        print(f"\n❌ Migration failed: {e}")
        raise
    finally:
        session.close()

if __name__ == "__main__":
    migrate()

# Made with Bob
