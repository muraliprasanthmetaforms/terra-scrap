#!/bin/bash

echo "🚀 Terra Scrap - Quick Deploy Script"
echo "==================================="

# Check if git is initialized
if [ ! -d ".git" ]; then
    echo "📝 Initializing git repository..."
    git init
    git branch -M main
fi

# Add all files
echo "📦 Adding files to git..."
git add .

# Commit
echo "💾 Creating commit..."
git commit -m "Deploy Terra Scrap v$(date +%Y%m%d_%H%M%S)"

echo ""
echo "✅ Ready for deployment!"
echo ""
echo "🌐 Choose your hosting platform:"
echo ""
echo "1️⃣  RAILWAY (Recommended)"
echo "   • Visit: https://railway.app"
echo "   • Connect GitHub account"
echo "   • Deploy from repository"
echo "   • Set environment variables:"
echo "     SECRET_KEY=your-long-random-secret-key"
echo "     MAIL_USERNAME=rgsiddhu5252@gmail.com"  
echo "     MAIL_PASSWORD=miblzeeoegkhtnbq"
echo ""
echo "2️⃣  RENDER"
echo "   • Visit: https://render.com"
echo "   • Connect GitHub repo"
echo "   • Auto-deploy from main branch"
echo ""
echo "3️⃣  HEROKU"
echo "   • Install Heroku CLI"
echo "   • Run: heroku create your-app-name"
echo "   • Set config vars"
echo "   • Push: git push heroku main"
echo ""
echo "🔗 Don't forget to:"
echo "   • Set environment variables"
echo "   • Test the deployed app"
echo "   • Share your app URL!"
echo ""
echo "📋 Your login credentials:"
echo "   Email: mprasanth18@gmail.com"
echo "   Password: IAmTheBest@1"