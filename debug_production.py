#!/usr/bin/env python3
"""
Debug script for production issues
Add this as a route in auth_app.py to debug production
"""

from flask import jsonify
import os
import sys
from datetime import datetime

def debug_info():
    """Return debug information for production troubleshooting"""
    info = {
        "timestamp": datetime.utcnow().isoformat(),
        "environment": {
            "SECRET_KEY_SET": bool(os.environ.get('SECRET_KEY')),
            "SECRET_KEY_LENGTH": len(os.environ.get('SECRET_KEY', '')),
            "MAIL_USERNAME": os.environ.get('MAIL_USERNAME', 'NOT_SET'),
            "MAIL_PASSWORD_SET": bool(os.environ.get('MAIL_PASSWORD')),
            "PORT": os.environ.get('PORT', 'NOT_SET'),
            "FLASK_ENV": os.environ.get('FLASK_ENV', 'NOT_SET'),
        },
        "python_info": {
            "version": sys.version,
            "platform": sys.platform,
        },
        "flask_config": {},
        "database": {
            "url": "Will check in app context",
        }
    }
    
    return info

# Add this route to your auth_app.py for debugging
DEBUG_ROUTE = '''
@app.route('/debug')
def debug_route():
    """Debug route - REMOVE IN PRODUCTION"""
    try:
        from debug_production import debug_info
        info = debug_info()
        
        # Add Flask app config
        info["flask_config"] = {
            "SECRET_KEY_SET": bool(app.config.get('SECRET_KEY')),
            "MAIL_SERVER": app.config.get('MAIL_SERVER'),
            "MAIL_PORT": app.config.get('MAIL_PORT'),
            "MAIL_USE_TLS": app.config.get('MAIL_USE_TLS'),
            "MAIL_USERNAME": app.config.get('MAIL_USERNAME'),
            "DATABASE_URI": app.config.get('SQLALCHEMY_DATABASE_URI'),
        }
        
        # Test database
        with app.app_context():
            try:
                user_count = User.query.count()
                info["database"] = {
                    "status": "connected",
                    "user_count": user_count,
                    "url": app.config.get('SQLALCHEMY_DATABASE_URI'),
                }
            except Exception as e:
                info["database"] = {
                    "status": "error",
                    "error": str(e),
                }
        
        return jsonify(info)
    except Exception as e:
        return jsonify({"error": str(e)})
'''

print("🔍 Production Debug Script")
print("=" * 30)
print("Add the DEBUG_ROUTE code to your auth_app.py file")
print("Then visit https://your-app.railway.app/debug")
print("This will show configuration and database status")