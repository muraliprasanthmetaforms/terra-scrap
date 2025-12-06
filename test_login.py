#!/usr/bin/env python3
"""
Test login functionality programmatically
"""

import requests
import sys

def test_login():
    """Test login via HTTP requests"""
    print("🧪 Testing Terra Scrap Login")
    print("=" * 35)
    
    base_url = "http://127.0.0.1:5000"
    
    # Test if server is running
    try:
        response = requests.get(base_url, timeout=5)
        print(f"✅ Server is running (status: {response.status_code})")
    except requests.exceptions.RequestException as e:
        print(f"❌ Server is not accessible: {e}")
        print("Make sure the app is running with: uv run --no-project python3 auth_app.py")
        return
    
    # Test login
    login_data = {
        'username': 'mprasanth18@gmail.com',  # Using email as username
        'password': 'IAmTheBest@1',
        'submit': 'Sign In'
    }
    
    session = requests.Session()
    
    try:
        # Get login page first (for CSRF token if needed)
        login_page = session.get(f"{base_url}/login")
        print(f"📝 Login page status: {login_page.status_code}")
        
        # Attempt login
        login_response = session.post(f"{base_url}/login", data=login_data, allow_redirects=False)
        print(f"🔐 Login attempt status: {login_response.status_code}")
        
        if login_response.status_code == 302:  # Redirect means success
            print("✅ Login successful! (redirected)")
            redirect_location = login_response.headers.get('Location', 'Unknown')
            print(f"   Redirected to: {redirect_location}")
        elif login_response.status_code == 200:
            print("⚠️  Login returned 200 (likely failed)")
            if "Invalid" in login_response.text:
                print("   Error: Invalid credentials detected")
            elif "pending approval" in login_response.text.lower():
                print("   Error: Account pending approval")
        else:
            print(f"❌ Unexpected response: {login_response.status_code}")
            
    except Exception as e:
        print(f"❌ Login test failed: {e}")

if __name__ == "__main__":
    test_login()