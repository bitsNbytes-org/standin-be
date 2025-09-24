#!/usr/bin/env python3
"""
Migration script for running Alembic migrations
"""
import subprocess
import sys
import time
import os

def run_migrations():
    """Run Alembic migrations"""
    try:
        print("Running database migrations...")
        result = subprocess.run(
            ["alembic", "upgrade", "head"],
            check=True,
            capture_output=True,
            text=True
        )
        print("✅ Migrations completed successfully!")
        print(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print("❌ Migration failed!")
        print(f"Error: {e.stderr}")
        return False
    except FileNotFoundError:
        print("❌ Alembic not found. Make sure it's installed.")
        return False

def wait_for_db(max_retries=30, delay=2):
    """Wait for database to be ready"""
    print("Waiting for database to be ready...")
    
    for attempt in range(max_retries):
        try:
            # Try to connect to database using alembic
            result = subprocess.run(
                ["alembic", "current"],
                check=True,
                capture_output=True,
                text=True
            )
            print("✅ Database is ready!")
            return True
        except subprocess.CalledProcessError:
            if attempt < max_retries - 1:
                print(f"Database not ready, retrying in {delay} seconds... ({attempt + 1}/{max_retries})")
                time.sleep(delay)
            else:
                print("❌ Database connection timeout!")
                return False
    
    return False

if __name__ == "__main__":
    print("🚀 Starting migration process...")
    
    # Wait for database to be ready
    if not wait_for_db():
        sys.exit(1)
    
    # Run migrations
    if not run_migrations():
        sys.exit(1)
    
    print("🎉 Migration process completed!")
