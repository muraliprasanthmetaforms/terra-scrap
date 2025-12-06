# 🚀 Terra Scrap with UV - Quick Setup Guide

## Why UV?
UV is **10-100x faster** than pip for installing Python packages! Perfect for getting Terra Scrap up and running quickly.

## 🏃‍♂️ Super Quick Start

```bash
# 1. Install dependencies (lightning fast with uv)
uv pip install flask flask-sqlalchemy flask-login flask-wtf flask-mail wtforms werkzeug requests beautifulsoup4 lxml email-validator

# 2. Initialize database
python init_db.py

# 3. Start the application
python auth_app.py
```

That's it! Your Terra Scrap platform is running at `http://localhost:5000` 🎉

## 🔧 UV Project Setup (Alternative)

If you want to use project configurations:

```bash
# Option 1: Install from requirements.txt (recommended)
uv pip install -r requirements.txt

# Option 2: Install from pyproject.toml (production dependencies only)
uv pip install .

# Run with python (using uv-managed packages)
python auth_app.py
```

## 🐛 Development with UV

```bash
# Install development dependencies
uv pip install -e ".[dev]"

# Run tests (when available)
uv run pytest

# Format code
uv run black .

# Lint code
uv run flake8 .
```

## 🌐 Running the Scraper

```bash
# Start the main application
python auth_app.py

# Initialize database (only needed once)
python init_db.py

# Migrate from old version (if needed)
python migrate_from_old.py
```

## 💡 Pro Tips with UV

1. **Install UV first**: `pip install uv` or `curl -LsSf https://astral.sh/uv/install.sh | sh`
2. **UV is much faster**: Installs packages in seconds vs minutes
3. **Works with any Python version**: UV handles Python version management too
4. **Drop-in replacement**: Use `uv pip` instead of `pip` in most cases

## 🚨 First Time Setup Checklist

- [ ] Install uv: `pip install uv`
- [ ] Install dependencies: `uv pip install flask flask-sqlalchemy flask-login flask-wtf flask-mail wtforms werkzeug requests beautifulsoup4 lxml email-validator`
- [ ] Initialize database: `python init_db.py`
- [ ] Start application: `python auth_app.py`
- [ ] Visit `http://localhost:5000` and create account
- [ ] Check admin email (rgsiddhu5252@gmail.com) for approval
- [ ] Sign in and start scraping! 🎯

## 🔄 Switching from pip

If you're currently using pip, you can easily switch:

```bash
# Instead of: pip install -r requirements.txt
uv pip install -r requirements.txt

# Then run scripts normally with python (using uv-managed packages)
python script.py

# For production install from pyproject.toml
uv pip install .
```

## ⚡ Troubleshooting

**If you get dependency resolution errors:**
1. Use the direct install method (fastest anyway):
   ```bash
   uv pip install flask flask-sqlalchemy flask-login flask-wtf flask-mail wtforms werkzeug requests beautifulsoup4 lxml email-validator
   ```

2. Or use requirements.txt:
   ```bash
   uv pip install -r requirements.txt
   ```

3. Avoid installing dev dependencies unless needed:
   ```bash
   # Don't use -e . if you're getting conflicts
   # Use . instead for production install
   uv pip install .
   ```

UV will automatically use your existing virtual environment or create one if needed!