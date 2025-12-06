#!/usr/bin/env python3
"""
Database initialization script for Terra Scrap
Run this script to create the database tables before starting the application.
"""

from auth_app import app, db, User
import sys

def init_database():
    """Initialize the database with required tables"""
    print("🌍 Terra Scrap - Database Initialization")
    print("=" * 45)
    
    try:
        with app.app_context():
            # Create all database tables
            db.create_all()
            print("✅ Database tables created successfully!")
            
            # Check if any users exist
            user_count = User.query.count()
            print(f"📊 Current user count: {user_count}")
            
            if user_count == 0:
                print("ℹ️  No users found. The first user to register will need admin approval.")
            else:
                print("👥 Existing users found in the database.")
            
            print("\n🚀 Database initialization complete!")
            print("\nNext steps:")
            print("1. Start the application: python auth_app.py")
            print("2. Visit http://localhost:5000/signup to create an account")
            print("3. Check admin email (rgsiddhu5252@gmail.com) for approval requests")
            print("4. Once approved, sign in and start scraping!")
            
    except Exception as e:
        print(f"❌ Error initializing database: {e}")
        sys.exit(1)

if __name__ == "__main__":
    init_database()