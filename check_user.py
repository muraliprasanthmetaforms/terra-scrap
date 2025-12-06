#!/usr/bin/env python3
"""
Check user database for debugging login issues
"""

from auth_app import app, db, User
import sys

def check_users():
    """Check all users in the database"""
    print("🔍 Terra Scrap - User Database Check")
    print("=" * 45)
    
    try:
        with app.app_context():
            users = User.query.all()
            
            if not users:
                print("❌ No users found in database!")
                return
            
            print(f"📊 Total users: {len(users)}")
            print()
            
            for i, user in enumerate(users, 1):
                print(f"User {i}:")
                print(f"  ID: {user.id}")
                print(f"  Username: {user.username}")
                print(f"  Email: {user.email}")
                print(f"  Approved: {'✅ Yes' if user.is_approved else '❌ No'}")
                print(f"  Active: {'✅ Yes' if user.is_active else '❌ No'}")
                print(f"  Created: {user.created_at}")
                print(f"  Password Hash: {user.password_hash[:20]}...")
                print()
            
            # Test password verification
            target_email = 'mprasanth18@gmail.com'
            target_password = 'IAmTheBest@1'
            
            user = User.query.filter_by(email=target_email).first()
            if user:
                print(f"🧪 Testing password for {target_email}:")
                if user.check_password(target_password):
                    print(f"✅ Password '{target_password}' is CORRECT")
                else:
                    print(f"❌ Password '{target_password}' is INCORRECT")
                
                print(f"🔐 Login Requirements:")
                print(f"   Username/Email: {user.username} or {user.email}")
                print(f"   Password: IAmTheBest@1")
                print(f"   Approved: {'✅' if user.is_approved else '❌ NEEDS APPROVAL'}")
                print(f"   Active: {'✅' if user.is_active else '❌ INACTIVE'}")
            else:
                print(f"❌ User with email {target_email} not found!")
                
    except Exception as e:
        print(f"❌ Error checking users: {e}")
        sys.exit(1)

if __name__ == "__main__":
    check_users()