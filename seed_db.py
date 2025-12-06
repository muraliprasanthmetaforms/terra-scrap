#!/usr/bin/env python3
"""
Database seeding script for Terra Scrap
Adds test users to the database for development and testing
"""

from auth_app import app, db, User
import sys

def seed_test_user():
    """Add test user to the database"""
    print("🌱 Terra Scrap - Database Seeding")
    print("=" * 40)
    
    try:
        with app.app_context():
            # Check if user already exists
            existing_user = User.query.filter_by(email='mprasanth18@gmail.com').first()
            if existing_user:
                print("⚠️  Test user already exists!")
                print(f"   Username: {existing_user.username}")
                print(f"   Email: {existing_user.email}")
                print(f"   Approved: {'Yes' if existing_user.is_approved else 'No'}")
                
                # Update approval status if needed
                if not existing_user.is_approved:
                    existing_user.is_approved = True
                    existing_user.approval_token = None  # Clear approval token
                    db.session.commit()
                    print("✅ User has been approved!")
                else:
                    print("✅ User is already approved!")
                
                return
            
            # Create new test user
            test_user = User(
                username='mprasanth18',
                email='mprasanth18@gmail.com'
            )
            test_user.set_password('IAmTheBest@1')
            test_user.is_approved = True  # Auto-approve for testing
            test_user.is_active = True
            
            db.session.add(test_user)
            db.session.commit()
            
            print("✅ Test user created successfully!")
            print(f"   Username: {test_user.username}")
            print(f"   Email: {test_user.email}")
            print(f"   Password: IAmTheBest@1")
            print(f"   Status: Approved ✅")
            
            print("\n🚀 Ready to test!")
            print("You can now sign in with:")
            print("  Username: mprasanth18")
            print("  Email: mprasanth18@gmail.com")
            print("  Password: IAmTheBest@1")
            
    except Exception as e:
        print(f"❌ Error seeding database: {e}")
        sys.exit(1)

def seed_additional_users():
    """Add additional test users if needed"""
    additional_users = [
        {
            'username': 'testuser1',
            'email': 'test1@example.com',
            'password': 'TestPass123!',
            'approved': True
        },
        {
            'username': 'testuser2',
            'email': 'test2@example.com',
            'password': 'TestPass123!',
            'approved': False  # This one needs approval
        }
    ]
    
    with app.app_context():
        for user_data in additional_users:
            existing = User.query.filter_by(email=user_data['email']).first()
            if not existing:
                user = User(
                    username=user_data['username'],
                    email=user_data['email']
                )
                user.set_password(user_data['password'])
                user.is_approved = user_data['approved']
                user.is_active = True
                
                if not user_data['approved']:
                    user.generate_approval_token()
                
                db.session.add(user)
        
        db.session.commit()
        print(f"✅ Added {len(additional_users)} additional test users")

if __name__ == "__main__":
    # Check command line arguments
    if len(sys.argv) > 1 and sys.argv[1] == '--all':
        seed_test_user()
        seed_additional_users()
        print("\n📊 Database Summary:")
        with app.app_context():
            total_users = User.query.count()
            approved_users = User.query.filter_by(is_approved=True).count()
            print(f"   Total users: {total_users}")
            print(f"   Approved users: {approved_users}")
            print(f"   Pending approval: {total_users - approved_users}")
    else:
        seed_test_user()