#!/usr/bin/env python3
"""
Fix the existing user's username to be simpler
"""

from auth_app import app, db, User
import sys

def fix_user():
    """Update the username to be simpler"""
    print("🔧 Terra Scrap - Fix User Username")
    print("=" * 40)
    
    try:
        with app.app_context():
            # Find the existing user
            user = User.query.filter_by(email='mprasanth18@gmail.com').first()
            if not user:
                print("❌ User not found!")
                return
            
            print(f"Current username: '{user.username}'")
            
            # Update username to be simpler
            user.username = 'mprasanth18'
            db.session.commit()
            
            print(f"✅ Updated username to: '{user.username}'")
            print("\nNow you can login with EITHER:")
            print(f"  Username: {user.username}")
            print(f"  Email: {user.email}")
            print(f"  Password: IAmTheBest@1")
            
    except Exception as e:
        print(f"❌ Error fixing user: {e}")
        sys.exit(1)

if __name__ == "__main__":
    fix_user()