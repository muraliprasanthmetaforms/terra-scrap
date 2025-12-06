#!/bin/bash

echo "🚀 Terra Scrap - Railway Deployment Script"
echo "========================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🌍 Deploying Terra Scrap to Railway (Free Hosting)${NC}"
echo -e "${YELLOW}💡 Perfect solution for your Hostinger Premium + Free Python hosting!${NC}"
echo ""

# Check if in correct directory
if [ ! -f "auth_app.py" ]; then
    echo -e "${RED}❌ Error: auth_app.py not found!${NC}"
    echo "Please run this script from the Terra Scrap directory"
    exit 1
fi

echo -e "${BLUE}📋 Step 1: Checking required files...${NC}"

# Check required files
REQUIRED_FILES=("auth_app.py" "requirements.txt" "Procfile")
for file in "${REQUIRED_FILES[@]}"; do
    if [ -f "$file" ]; then
        echo -e "  ✅ $file"
    else
        echo -e "  ❌ $file missing"
        if [ "$file" = "Procfile" ]; then
            echo "web: python auth_app.py" > Procfile
            echo -e "  ✅ Created Procfile"
        fi
    fi
done

echo -e "${BLUE}🔧 Step 2: Preparing deployment files...${NC}"

# Ensure .gitignore exists
if [ ! -f ".gitignore" ]; then
    cat > .gitignore << 'EOF'
__pycache__/
*.py[cod]
.env
*.db
*.sqlite
*.sqlite3
venv/
.venv/
EOF
    echo "✅ Created .gitignore"
fi

# Create railway.json for optimal deployment
cat > railway.json << 'EOF'
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "NIXPACKS"
  },
  "deploy": {
    "startCommand": "python auth_app.py",
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 10
  }
}
EOF
echo "✅ Created railway.json"

echo -e "${BLUE}📝 Step 3: Git setup...${NC}"

# Initialize git if not already done
if [ ! -d ".git" ]; then
    echo "Initializing git repository..."
    git init
    git branch -M main
fi

# Add all files
git add .

# Create commit
COMMIT_MSG="Deploy Terra Scrap to Railway - $(date +%Y-%m-%d_%H:%M:%S)"
git commit -m "$COMMIT_MSG"

echo -e "${GREEN}✅ Git repository prepared!${NC}"

echo ""
echo -e "${GREEN}🎉 Ready for Railway Deployment!${NC}"
echo "=================================="
echo ""
echo -e "${BLUE}📋 Next Steps:${NC}"
echo ""
echo "1️⃣  **Create GitHub Repository:**"
echo "   • Go to github.com and create new repository 'terra-scrap'"
echo "   • Run: git remote add origin https://github.com/YOURUSERNAME/terra-scrap.git"
echo "   • Run: git push -u origin main"
echo ""
echo "2️⃣  **Deploy on Railway:**"
echo "   • Visit: https://railway.app"
echo "   • Sign up with GitHub account"
echo "   • Click 'Deploy from GitHub repo'"
echo "   • Select your terra-scrap repository"
echo "   • Wait for deployment (2-3 minutes)"
echo ""
echo "3️⃣  **Set Environment Variables in Railway:**"
echo "   • Go to your app → Variables tab"
echo "   • Add these variables:"
echo -e "     ${YELLOW}SECRET_KEY${NC} = $(openssl rand -hex 32 2>/dev/null || echo 'your-long-random-secret-key-change-this')"
echo -e "     ${YELLOW}MAIL_USERNAME${NC} = rgsiddhu5252@gmail.com"
echo -e "     ${YELLOW}MAIL_PASSWORD${NC} = miblzeeoegkhtnbq"
echo ""
echo "4️⃣  **Test Your App:**"
echo "   • Railway will give you a URL like: https://your-app.railway.app"
echo "   • Login with: mprasanth18@gmail.com / IAmTheBest@1"
echo "   • Start scraping! 🚀"
echo ""
echo -e "${GREEN}💡 Pro Tip: Railway + Your Hostinger Premium = Perfect Combo!${NC}"
echo "   • Main website: yourdomain.com (Hostinger Premium)"
echo "   • Scraper app: scraper.yourdomain.com (Railway - FREE)"
echo ""
echo -e "${BLUE}🔧 Optional - Custom Domain Setup:${NC}"
echo "   • In Railway: Add custom domain 'scraper.yourdomain.com'"
echo "   • In Hostinger DNS: Add CNAME record pointing to Railway"
echo ""
echo -e "${YELLOW}💰 Cost: $0/month (Railway free tier is perfect for Terra Scrap!)${NC}"
echo ""
echo -e "${GREEN}Terra Scrap is ready for Railway deployment! 🌟${NC}"