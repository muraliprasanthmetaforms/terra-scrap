# 🌐 Terra Scrap - Hostinger Deployment Guide

## 📋 Hostinger Hosting Options

### 1. Hostinger VPS (Recommended for Terra Scrap) 💰

**Why VPS?**
- Full server control
- Python support out of the box
- Can install any packages
- Run background processes
- Suitable for web scraping applications

**Plans:**
- VPS 1: ~$3.99/month (1 vCPU, 1GB RAM)
- VPS 2: ~$5.99/month (2 vCPU, 2GB RAM) - **Recommended**
- VPS 3: ~$8.99/month (3 vCPU, 3GB RAM)

### 2. Hostinger Shared Hosting ⚠️

**Limitations:**
- Limited Python support
- No long-running processes
- Restricted package installation
- **NOT recommended for Terra Scrap** (web scraping needs background processes)

## 🚀 VPS Deployment Steps

### Step 1: VPS Setup

1. **Purchase Hostinger VPS**
   - Go to [hostinger.com](https://hostinger.com)
   - Choose VPS hosting plan
   - Select Ubuntu 20.04 or 22.04 as OS

2. **Access your VPS**
   ```bash
   # Use SSH (credentials provided by Hostinger)
   ssh root@your-vps-ip
   ```

### Step 2: Server Preparation

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Python and pip
sudo apt install python3 python3-pip python3-venv git nginx -y

# Install UV (optional - for faster package management)
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc
```

### Step 3: Deploy Terra Scrap

```bash
# Clone your repository (upload via git or SFTP)
git clone https://github.com/yourusername/terra-scrap.git
cd terra-scrap

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
# OR with UV (faster)
# uv pip install -r requirements.txt

# Set environment variables
export SECRET_KEY="your-long-random-secret-key-here"
export MAIL_USERNAME="rgsiddhu5252@gmail.com"
export MAIL_PASSWORD="miblzeeoegkhtnbq"
export PORT="5000"

# Initialize database
python3 init_db.py
python3 seed_db.py

# Test the application
python3 auth_app.py
```

### Step 4: Production Setup with Nginx + Gunicorn

**Install Gunicorn:**
```bash
pip install gunicorn
```

**Create Gunicorn service file:**
```bash
sudo nano /etc/systemd/system/terrascrap.service
```

**Add this content:**
```ini
[Unit]
Description=Terra Scrap Web Application
After=network.target

[Service]
User=root
Group=root
WorkingDirectory=/root/terra-scrap
Environment="PATH=/root/terra-scrap/venv/bin"
Environment="SECRET_KEY=your-long-random-secret-key-here"
Environment="MAIL_USERNAME=rgsiddhu5252@gmail.com"
Environment="MAIL_PASSWORD=miblzeeoegkhtnbq"
Environment="PORT=5000"
ExecStart=/root/terra-scrap/venv/bin/gunicorn --workers 2 --bind 127.0.0.1:5000 auth_app:app
Restart=always

[Install]
WantedBy=multi-user.target
```

**Create Nginx configuration:**
```bash
sudo nano /etc/nginx/sites-available/terrascrap
```

**Add this content:**
```nginx
server {
    listen 80;
    server_name your-domain.com www.your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Handle static files (if any)
    location /static {
        alias /root/terra-scrap/static;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
```

**Enable and start services:**
```bash
# Enable Nginx site
sudo ln -s /etc/nginx/sites-available/terrascrap /etc/nginx/sites-enabled
sudo nginx -t
sudo systemctl reload nginx

# Start Terra Scrap service
sudo systemctl daemon-reload
sudo systemctl enable terrascrap
sudo systemctl start terrascrap

# Check status
sudo systemctl status terrascrap
```

## 🔒 SSL Setup (Optional but Recommended)

**Install Certbot:**
```bash
sudo apt install certbot python3-certbot-nginx -y

# Get SSL certificate
sudo certbot --nginx -d your-domain.com -d www.your-domain.com
```

## 🌐 Domain Setup

1. **Point your domain to VPS IP:**
   - A record: `your-domain.com` → `your-vps-ip`
   - A record: `www.your-domain.com` → `your-vps-ip`

2. **Update Nginx config with your domain**

## 📊 Monitoring & Maintenance

**Check application logs:**
```bash
sudo journalctl -u terrascrap -f
```

**Restart application:**
```bash
sudo systemctl restart terrascrap
```

**Update application:**
```bash
cd /root/terra-scrap
git pull
sudo systemctl restart terrascrap
```

## 💰 Hostinger Cost Breakdown

**Monthly Costs:**
- VPS 2 (Recommended): $5.99/month
- Domain (optional): ~$1-15/year
- **Total: ~$6-7/month**

**What you get:**
- Full server control
- Your own IP address
- Can run 24/7 scraping
- Professional setup
- SSL certificate (free with Let's Encrypt)

## 🔧 Alternative: Quick Setup Script

Create this script on your VPS:

```bash
#!/bin/bash
# save as setup-terrascrap.sh

echo "🌍 Setting up Terra Scrap on Hostinger VPS"

# System updates
sudo apt update && sudo apt upgrade -y
sudo apt install python3 python3-pip python3-venv git nginx -y

# Clone repository (replace with your repo)
git clone https://github.com/yourusername/terra-scrap.git
cd terra-scrap

# Python setup
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt gunicorn

# Environment setup
echo "export SECRET_KEY='$(openssl rand -hex 32)'" >> ~/.bashrc
echo "export MAIL_USERNAME='rgsiddhu5252@gmail.com'" >> ~/.bashrc
echo "export MAIL_PASSWORD='miblzeeoegkhtnbq'" >> ~/.bashrc
source ~/.bashrc

# Initialize app
python3 init_db.py
python3 seed_db.py

echo "✅ Setup complete! Configure Nginx and systemd service next."
```

## 📞 Hostinger Support

- **24/7 Live Chat** support
- **Knowledge Base** with tutorials
- **Email Support** for technical issues
- **VPS Management Panel** for server control

## 🎯 Pros & Cons

**Pros:**
- ✅ Affordable VPS hosting
- ✅ Full server control
- ✅ Good performance
- ✅ 24/7 support
- ✅ Easy domain management

**Cons:**
- ❌ Requires more technical setup than Railway/Render
- ❌ You manage the server yourself
- ❌ Need to handle security updates

## 🚀 Quick Start Summary

1. **Buy Hostinger VPS 2** (~$6/month)
2. **SSH into server**
3. **Run setup commands** (see above)
4. **Configure domain** (optional)
5. **Set up SSL** with Certbot
6. **Monitor and maintain**

**Perfect for:** Users who want full control and don't mind managing a server.

**Alternative:** If you prefer simpler deployment, stick with **Railway** or **Render** from the previous guide!