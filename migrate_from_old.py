#!/usr/bin/env python3
"""
Migration script to help transition from the old sky.py single-website scraper
to the new multi-website Terra Scrap application.
"""

import os
import shutil
from datetime import datetime

def migrate_old_scraper():
    """Migrate data and configuration from old scraper"""
    
    print("🌍 Terra Scrap Migration Tool")
    print("=" * 40)
    
    # Check if old files exist
    old_csv = "job_contacts_live.csv"
    new_csv = "make_it_germany_jobs.csv"
    
    if os.path.exists(old_csv):
        print(f"✅ Found old CSV file: {old_csv}")
        
        # Create backup
        backup_name = f"backup_{old_csv}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        shutil.copy2(old_csv, backup_name)
        print(f"📁 Created backup: {backup_name}")
        
        # Copy to new format
        if not os.path.exists(new_csv):
            shutil.copy2(old_csv, new_csv)
            print(f"📋 Migrated data to: {new_csv}")
        else:
            print(f"⚠️  {new_csv} already exists. Skipping migration.")
    else:
        print(f"ℹ️  No old CSV file found ({old_csv})")
    
    print("\n🚀 Migration complete!")
    print("\nNext steps:")
    print("1. Install dependencies: pip install flask requests beautifulsoup4 lxml")
    print("2. Run the new application: python app.py")
    print("3. Visit http://localhost:5000 in your browser")
    print("4. Select 'Make-it-in-Germany' scraper to continue where you left off")

if __name__ == "__main__":
    migrate_old_scraper()