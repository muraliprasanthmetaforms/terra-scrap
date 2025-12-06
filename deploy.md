# 🚀 Terra Scrap - Deployment Guide

## 🌐 Free Hosting Options

### 1. Railway (Recommended) ⭐

**Why Railway?**
- Free tier with generous limits
- Automatic deployments from GitHub
- Built-in SQLite support
- Easy environment variable management
- Custom domains

**Steps:**
1. **Prepare for deployment:**
   ```bash
   # Create Procfile
   echo "web: python auth_app.py" > Procfile
   
   # Update auth_app.py for production
   # Add at the bottom, replace the last line:
   if __name__ == "__main__":
       import os
       port = int(os.environ.get("PORT", 5000))
       with app.app_context():
           db.create_all()
       app.run(host="0.0.0.0", port=port, debug=False)
   ```

2. **Push to GitHub:**
   ```bash
   git init
   git add .
   git commit -m "Initial Terra Scrap deployment"
   git remote add origin https://github.com/yourusername/terra-scrap.git
   git push -u origin main
   ```

3. **Deploy on Railway:**
   - Visit [railway.app](https://railway.app)
   - Connect GitHub account
   - Deploy from your repository
   - Set environment variables:
     ```
     SECRET_KEY=your-super-secret-production-key-here
     MAIL_USERNAME=rgsiddhu5252@gmail.com
     MAIL_PASSWORD=miblzeeoegkhtnbq
     ```

### 2. Render.com

**Steps:**
1. **Create render.yaml:**
   ```yaml
   services:
     - type: web
       name: terra-scrap
       env: python
       buildCommand: "pip install -r requirements.txt"
       startCommand: "python auth_app.py"
       envVars:
         - key: SECRET_KEY
           generateValue: true
         - key: MAIL_USERNAME
           value: rgsiddhu5252@gmail.com
         - key: MAIL_PASSWORD
           value: miblzeeoegkhtnbq
   ```

2. **Deploy:** Connect GitHub repo on render.com

### 3. Heroku

**Steps:**
1. **Install Heroku CLI**
2. **Create Procfile:** `web: python auth_app.py`
3. **Deploy:**
   ```bash
   heroku create terra-scrap-app
   heroku config:set SECRET_KEY=your-secret-key
   heroku config:set MAIL_USERNAME=rgsiddhu5252@gmail.com
   heroku config:set MAIL_PASSWORD=miblzeeoegkhtnbq
   git push heroku main
   ```

## 🔧 Production Setup

### 1. Update auth_app.py for Production

Add this at the end of auth_app.py:

```python
# Production configuration
if __name__ == "__main__":
    import os
    
    # Environment variables
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'terra-scrap-secret-key-change-in-production')
    
    # Email config from environment
    app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME', 'rgsiddhu5252@gmail.com')
    app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD', 'miblzeeoegkhtnbq')
    
    # Database
    database_url = os.environ.get('DATABASE_URL', 'sqlite:///terra_scrap.db')
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    
    # Create tables
    with app.app_context():
        db.create_all()
        
        # Seed test user in production
        existing_user = User.query.filter_by(email='mprasanth18@gmail.com').first()
        if not existing_user:
            test_user = User(username='mprasanth18', email='mprasanth18@gmail.com')
            test_user.set_password('IAmTheBest@1')
            test_user.is_approved = True
            test_user.is_active = True
            db.session.add(test_user)
            db.session.commit()
    
    # Run app
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
```

### 2. Create Production Files

**Procfile:**
```
web: python auth_app.py
```

**runtime.txt:** (optional)
```
python-3.11.0
```

### 3. Environment Variables

Set these in your hosting platform:

```bash
SECRET_KEY=your-super-secret-production-key-here-make-it-long-and-random
MAIL_USERNAME=rgsiddhu5252@gmail.com
MAIL_PASSWORD=miblzeeoegkhtnbq
PORT=5000
```

## 📋 Pre-Deployment Checklist

- [ ] ✅ Update `SECRET_KEY` to a secure random string
- [ ] ✅ Test email functionality locally
- [ ] ✅ Create Procfile
- [ ] ✅ Update auth_app.py with production config
- [ ] ✅ Push code to GitHub
- [ ] ✅ Set environment variables on hosting platform
- [ ] ✅ Deploy and test
- [ ] ✅ Test user registration/approval flow
- [ ] ✅ Test scraper functionality

## 🎯 Quick Deploy Commands

### For Railway:
```bash
# 1. Prepare
echo "web: python auth_app.py" > Procfile

# 2. Git setup
git init
git add .
git commit -m "Deploy Terra Scrap"

# 3. Deploy on railway.app (web interface)
```

### For Render:
```bash
# 1. Create render.yaml (see above)
# 2. Push to GitHub
# 3. Connect on render.com
```

### For Heroku:
```bash
# 1. Setup
heroku create your-app-name
echo "web: python auth_app.py" > Procfile

# 2. Config
heroku config:set SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")
heroku config:set MAIL_USERNAME=rgsiddhu5252@gmail.com
heroku config:set MAIL_PASSWORD=miblzeeoegkhtnbq

# 3. Deploy
git add . && git commit -m "Deploy"
git push heroku main
```

## 🔗 After Deployment

1. **Test the application**
2. **Sign up/login with your test account**
3. **Test scraping functionality**
4. **Share your app URL**: `https://your-app-name.railway.app`

## 💡 Tips

- **Railway** is the easiest and most reliable
- **Environment variables** keep secrets safe
- **SQLite** works great for small to medium usage
- **Monitor logs** through your hosting platform's dashboard
- **Custom domains** available on most platforms

Choose Railway for the simplest deployment experience!