#!/bin/bash

# Terra Scrap - UV Runner Script
# This script helps you run Terra Scrap with UV-managed dependencies

echo "🌍 Terra Scrap - UV Runner"
echo "========================="

# Function to run commands with UV's python
run_with_uv() {
    echo "Running: uv run --no-project python3 $1"
    uv run --no-project python3 "$1"
}

# Check command line arguments
if [ $# -eq 0 ]; then
    echo "Usage: ./run.sh [init|seed|start|help]"
    echo ""
    echo "Commands:"
    echo "  init  - Initialize database"
    echo "  seed  - Add test user (mprasanth18@gmail.com / IAmTheBest@1)"
    echo "  start - Start Terra Scrap application"  
    echo "  help  - Show this help message"
    echo ""
    echo "Or run directly:"
    echo "  uv run --no-project python3 init_db.py"
    echo "  uv run --no-project python3 seed_db.py"
    echo "  uv run --no-project python3 auth_app.py"
    exit 1
fi

case "$1" in
    "init")
        echo "🔧 Initializing database..."
        run_with_uv "init_db.py"
        ;;
    "seed")
        echo "🌱 Adding test user..."
        run_with_uv "seed_db.py"
        ;;
    "start")
        echo "🚀 Starting Terra Scrap..."
        run_with_uv "auth_app.py"
        ;;
    "help")
        echo "Commands:"
        echo "  ./run.sh init  - Initialize database"
        echo "  ./run.sh seed  - Add test user"
        echo "  ./run.sh start - Start application"
        ;;
    *)
        echo "❌ Unknown command: $1"
        echo "Use: ./run.sh help for available commands"
        exit 1
        ;;
esac