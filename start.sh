#!/bin/bash

# Terra Scrap Quick Start Script
# Use this if run.sh has issues

echo "🌍 Terra Scrap - Quick Start"
echo "============================"

# Try different methods to run the application

echo "Method 1: Direct UV commands"
echo "1. Add test user:"
echo "   uv run --no-project python3 seed_db.py"
echo ""
echo "2. Start application:"  
echo "   uv run --no-project python3 auth_app.py"
echo ""

echo "Method 2: Using virtual environment"
echo "1. Create and activate venv:"
echo "   python3 -m venv .venv && source .venv/bin/activate"
echo ""
echo "2. Install dependencies:"
echo "   uv pip install flask flask-sqlalchemy flask-login flask-wtf flask-mail wtforms werkzeug requests beautifulsoup4 lxml email-validator"
echo ""
echo "3. Run commands:"
echo "   python3 seed_db.py"
echo "   python3 auth_app.py"
echo ""

echo "Method 3: Traditional pip"
echo "1. Create venv and install:"
echo "   python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
echo ""
echo "2. Run:"
echo "   python3 seed_db.py"
echo "   python3 auth_app.py"
echo ""

echo "Choose the method that works best for your system!"
echo ""
echo "Your test user credentials:"
echo "  Username: mprasanth18"
echo "  Email: mprasanth18@gmail.com"
echo "  Password: IAmTheBest@1"