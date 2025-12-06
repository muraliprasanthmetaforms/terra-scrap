#!/bin/bash

echo "🌍 Terra Scrap - Hostinger VPS Setup Script"
echo "==========================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}📋 This script will set up Terra Scrap on your Hostinger VPS${NC}"
echo -e "${YELLOW}⚠️  Make sure you're running this on your Hostinger VPS server!${NC}"
echo ""

# Confirm before proceeding
read -p "Do you want to proceed? (y/n): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Setup cancelled."
    exit 1
fi

echo -e "${BLUE}🔄 Step 1: Updating system packages...${NC}"
sudo apt update && sudo apt upgrade -y

echo -e "${BLUE}📦 Step 2: Installing required packages...${NC}"
sudo apt install python3 python3-pip python3-venv git nginx supervisor -y

echo -e "${BLUE}🐍 Step 3: Installing UV (fast Python package manager)...${NC}"
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc

echo -e "${BLUE}📂 Step 4: Setting up Terra Scrap...${NC}"
# If running from inside the terra-scrap directory
if [ -f "auth_app.py" ]; then
    echo "✅ Already in Terra Scrap directory"
    TERRA_DIR=$(pwd)
else
    # If Terra Scrap needs to be cloned or found
    echo "📥 Please ensure Terra Scrap files are uploaded to your VPS"
    echo "You can:"
    echo "1. Upload files via SFTP/FTP"
    echo "2. Clone from GitHub: git clone https://github.com/yourusername/terra-scrap.git"
    echo ""
    read -p "Enter the path to Terra Scrap directory: " TERRA_DIR
    cd "$TERRA_DIR" || exit 1
fi

echo -e "${BLUE}🐍 Step 5: Creating virtual environment...${NC}"
python3 -m venv venv
source venv/bin/activate

echo -e "${BLUE}📦 Step 6: Installing Python dependencies...${NC}"
if command -v uv >/dev/null 2>&1; then
    echo "Using UV for faster installation..."
    uv pip install -r requirements.txt gunicorn
else
    echo "Using pip..."
    pip install -r requirements.txt gunicorn
fi

echo -e "${BLUE}🔑 Step 7: Setting up environment variables...${NC}"
SECRET_KEY=$(openssl rand -hex 32)

# Create environment file
cat > .env << EOF
SECRET_KEY=$SECRET_KEY
MAIL_USERNAME=rgsiddhu5252@gmail.com
MAIL_PASSWORD=miblzeeoegkhtnbq
PORT=5000
FLASK_ENV=production
EOF

echo "✅ Environment variables saved to .env file"

echo -e "${BLUE}🗄️  Step 8: Initializing database...${NC}"
source .env
python3 init_db.py
python3 seed_db.py

echo -e "${BLUE}⚙️  Step 9: Creating systemd service...${NC}"
sudo tee /etc/systemd/system/terrascrap.service > /dev/null << EOF
[Unit]
Description=Terra Scrap Web Application
After=network.target

[Service]
User=$USER
Group=$USER
WorkingDirectory=$TERRA_DIR
Environment="PATH=$TERRA_DIR/venv/bin"
EnvironmentFile=$TERRA_DIR/.env
ExecStart=$TERRA_DIR/venv/bin/gunicorn --workers 2 --bind 127.0.0.1:5000 auth_app:app
Restart=always

[Install]
WantedBy=multi-user.target
EOF

echo -e "${BLUE}🌐 Step 10: Configuring Nginx...${NC}"
sudo tee /etc/nginx/sites-available/terrascrap > /dev/null << 'EOF'
server {
    listen 80;
    server_name _;  # Replace with your domain

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;
    }

    client_max_body_size 100M;
}
EOF

# Enable the site
sudo ln -sf /etc/nginx/sites-available/terrascrap /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default

# Test nginx configuration
if sudo nginx -t; then
    echo -e "${GREEN}✅ Nginx configuration is valid${NC}"
else
    echo -e "${RED}❌ Nginx configuration error${NC}"
    exit 1
fi

echo -e "${BLUE}🚀 Step 11: Starting services...${NC}"
sudo systemctl daemon-reload
sudo systemctl enable terrascrap
sudo systemctl start terrascrap
sudo systemctl reload nginx

echo -e "${BLUE}📊 Step 12: Checking service status...${NC}"
sleep 3

if sudo systemctl is-active --quiet terrascrap; then
    echo -e "${GREEN}✅ Terra Scrap service is running${NC}"
else
    echo -e "${RED}❌ Terra Scrap service failed to start${NC}"
    echo "Check logs with: sudo journalctl -u terrascrap -n 50"
fi

if sudo systemctl is-active --quiet nginx; then
    echo -e "${GREEN}✅ Nginx is running${NC}"
else
    echo -e "${RED}❌ Nginx failed to start${NC}"
fi

echo ""
echo -e "${GREEN}🎉 Setup Complete!${NC}"
echo "=================================="
echo ""
echo -e "${BLUE}📝 Next Steps:${NC}"
echo "1. Get your VPS IP address: curl ipecho.net/plain"
echo "2. Visit http://YOUR-VPS-IP in your browser"
echo "3. Login with:"
echo "   Email: mprasanth18@gmail.com"
echo "   Password: IAmTheBest@1"
echo ""
echo -e "${BLUE}🌐 Optional - Domain Setup:${NC}"
echo "1. Point your domain to VPS IP"
echo "2. Update Nginx config: sudo nano /etc/nginx/sites-available/terrascrap"
echo "3. Install SSL: sudo apt install certbot python3-certbot-nginx -y"
echo "4. Get certificate: sudo certbot --nginx -d yourdomain.com"
echo ""
echo -e "${BLUE}🔧 Useful Commands:${NC}"
echo "- Check app logs: sudo journalctl -u terrascrap -f"
echo "- Restart app: sudo systemctl restart terrascrap"
echo "- Check status: sudo systemctl status terrascrap"
echo "- Update app: cd $TERRA_DIR && git pull && sudo systemctl restart terrascrap"
echo ""
echo -e "${GREEN}Terra Scrap is now running on your Hostinger VPS! 🚀${NC}"