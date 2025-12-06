# 🌍 Terra Scrap - Multi-Website Scraping Platform

A powerful Flask-based web scraping application with **user authentication** and **email verification** that supports multiple websites with a beautiful home page interface to select and manage different scrapers.

## Features

✨ **Multi-Website Support**: Easily add scrapers for different job sites  
🔐 **User Authentication**: Secure signin/signup with email verification  
📧 **Email Approval System**: Admin approval workflow for new users  
🔑 **Password Reset**: Forgot password functionality via email  
🎨 **Beautiful UI**: Modern, responsive interface with real-time updates  
📊 **Live Data Streaming**: Watch results appear in real-time as they're scraped  
📁 **CSV Export**: Download full, unique, or duplicate data sets  
🔍 **Advanced Filtering**: Search through results instantly  
🛡️ **Robust Extraction**: Smart contact and email extraction with error handling  
💾 **SQLite Database**: Free, lightweight database for user management  

## Quick Start with UV

1. **Install Dependencies (Choose One)**
   ```bash
   # Option 1: Direct install (fastest, recommended)
   uv pip install flask flask-sqlalchemy flask-login flask-wtf flask-mail wtforms werkzeug requests beautifulsoup4 lxml email-validator
   
   # Option 2: Install from requirements.txt
   uv pip install -r requirements.txt
   
   # Option 3: Install from pyproject.toml (production only)
   uv pip install .
   ```

2. **Initialize Database**
   ```bash
   python init_db.py
   ```

3. **Run the Application**
   ```bash
   python auth_app.py
   ```

4. **Create Account & Get Started**
   - Navigate to `http://localhost:5000`
   - You'll be redirected to the login page
   - Click "Create Account" to sign up
   - Wait for admin approval email
   - Once approved, sign in and start scraping!

## Alternative: Traditional pip

If you prefer using pip:

1. **Create Virtual Environment & Install**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Initialize Database**
   ```bash
   python init_db.py
   ```

3. **Run Application**
   ```bash
   python auth_app.py
   ```

## How to Use

### Authentication Flow
1. **Sign Up**: Create account with username, email, and password
2. **Admin Approval**: Admin receives email notification with approve/reject options
3. **Email Confirmation**: User gets confirmation email when approved
4. **Sign In**: Access the platform with approved credentials
5. **Password Reset**: Use "Forgot Password" if needed

### Home Page (Protected)
- View all available scrapers in a beautiful card layout
- Each card shows the scraper name, description, and target URL
- Click "Launch Scraper" to go to the individual scraper page
- User info and logout option in top navigation

### Individual Scraper Page (Protected)
- Set start and end page numbers for scraping
- Click "Run Scraper" to begin extraction
- Watch live results stream in the table
- Download CSV files (all data, unique emails, or duplicates)
- Use the search box to filter results in real-time

## Current Scrapers

### Make-it-in-Germany
- **Target**: https://www.make-it-in-germany.com/en/working-in-germany/job-listings
- **Description**: Official portal for international professionals seeking jobs in Germany
- **Data Extracted**: Job titles, companies, contact persons, emails, reference numbers, workplaces, employment types, and more

## Adding New Scrapers

To add a new website scraper, follow these steps:

### 1. Create a New Scraper Class

```python
class YourWebsiteScraper(BaseScraper):
    def get_name(self):
        return "Your Website Name"
    
    def get_description(self):
        return "Description of what this scraper does"
    
    def get_base_url(self):
        return "https://example.com/jobs?page="
    
    def get_csv_filename(self):
        return "your_website_jobs.csv"
    
    def parse_listing_page(self, html: str, base_url: str) -> List[Dict]:
        # Parse the listing page HTML
        # Return list of job dictionaries with 'title', 'company', 'job_url'
        pass
    
    def extract_detail_fields(self, html: str) -> tuple:
        # Extract detailed information from individual job pages
        # Return tuple: (contact, email, refnum, workplace, job_offer_type, 
        #                employment_contract, online_since, website)
        pass
```

### 2. Register Your Scraper

Add your scraper to the `SCRAPERS` dictionary:

```python
SCRAPERS = {
    'make-it-germany': MakeItGermanyScraper(),
    'your-website': YourWebsiteScraper(),  # Add your scraper here
}
```

### 3. Implement Required Methods

- **`parse_listing_page()`**: Parse job listing pages and extract basic job info
- **`extract_detail_fields()`**: Extract detailed information from individual job pages
- Use the helper methods from `BaseScraper` for common tasks like text cleaning and HTTP requests

## Architecture

### Base Classes
- **`BaseScraper`**: Abstract base class with common scraping functionality
- **`MakeItGermanyScraper`**: Concrete implementation for Make-it-in-Germany

### Key Components
- **Flask Routes**: Handle web requests and API endpoints
- **Event Streaming**: Real-time updates via Server-Sent Events (SSE)
- **Threading**: Background scraping without blocking the UI
- **CSV Management**: Export functionality with duplicate detection

### File Structure
```
Terra Scrap/
├── auth_app.py          # Main application with authentication
├── app.py               # Original app (without auth)
├── init_db.py          # Database initialization script
├── pyproject.toml       # Python project configuration (uv compatible)
├── requirements.txt     # Python dependencies (pip fallback)
├── migrate_from_old.py  # Migration helper
├── README.md           # This documentation
├── terra_scrap.db      # SQLite database (created automatically)
└── *.csv              # Generated CSV files (one per scraper)
```

## Authentication System

### Email Configuration
The application uses Gmail SMTP for sending emails:
- **SMTP Server**: smtp.gmail.com:587
- **Admin Email**: rgsiddhu5252@gmail.com
- **App Password**: miblzeeoegkhtnbq (Gmail app-specific password)

### Database Schema
**Users Table**:
- `id` (Primary Key)
- `username` (Unique)
- `email` (Unique)
- `password_hash` (Bcrypt hashed)
- `is_approved` (Boolean - requires admin approval)
- `is_active` (Boolean)
- `created_at` (Timestamp)
- `approval_token` (UUID for approval links)
- `reset_token` (UUID for password reset)
- `reset_token_expires` (Timestamp)

### Security Features
- 🔐 Password hashing with Werkzeug
- 🎫 Session management with Flask-Login
- ⏰ Expiring password reset tokens (24 hours)
- 🛡️ CSRF protection with Flask-WTF
- 📧 Email verification workflow
- 👤 User approval system

### Email Templates
- **Approval Request**: Sent to admin with approve/reject buttons
- **Account Approved**: Welcome email to approved users
- **Password Reset**: Secure reset link with expiration

## Technical Details

### Data Fields Extracted
- Job Title
- Company Name
- Contact Person
- Email Address
- Job URL
- Reference Number
- Workplace/Location
- Type of Job Offer
- Employment Contract Type
- Online Since Date
- Company Website
- Source Page
- Index

### Error Handling
- Retry logic for failed HTTP requests
- Graceful handling of missing data fields
- Real-time error logging in the UI

### Performance Features
- Random delays between requests to avoid rate limiting
- Configurable timeouts and retry attempts
- Memory-efficient streaming of large datasets

## Contributing

To contribute a new scraper:

1. Fork the repository
2. Create a new scraper class following the pattern above
3. Test your scraper thoroughly
4. Submit a pull request with documentation

## License

This project is open source. Use responsibly and respect robots.txt files and website terms of service.

## Roadmap

🔄 **Coming Soon**:
- LinkedIn Jobs scraper
- Indeed scraper
- StepStone scraper
- Xing Jobs scraper
- User role management (admin/user roles)
- Advanced filtering options
- Data export to JSON/Excel formats
- Scheduled scraping
- Email notifications for completed scrapes
- User dashboard with scraping history
- API endpoints for programmatic access

## 🚀 UV Quick Start (TLDR)

**The fastest way to get Terra Scrap running:**

```bash
# Install dependencies (10-100x faster than pip!)
uv pip install flask flask-sqlalchemy flask-login flask-wtf flask-mail wtforms werkzeug requests beautifulsoup4 lxml email-validator

# Initialize & run (use python directly with uv-managed packages)
python init_db.py
python auth_app.py
```

Visit `http://localhost:5000` and you're ready to go! 🎉

**Alternative with requirements.txt:**
```bash
uv pip install -r requirements.txt
python init_db.py
python auth_app.py
```

See [uv-instructions.md](uv-instructions.md) for detailed UV setup guide.

---

## Deployment Guide

### Free Hosting Options

1. **Railway** (Recommended)
   - Connect GitHub repository
   - Automatic deployments
   - Free tier available
   - Built-in SQLite support

2. **Heroku**
   - Use Heroku Postgres (free tier)
   - Update database URL in config
   - Add email credentials as environment variables

3. **Render**
   - Free static sites and web services
   - Automatic SSL certificates
   - Easy environment variable management

### Environment Variables for Production
```bash
SECRET_KEY=your-super-secret-key-change-this
MAIL_USERNAME=rgsiddhu5252@gmail.com
MAIL_PASSWORD=miblzeeoegkhtnbq
DATABASE_URL=sqlite:///terra_scrap.db  # or PostgreSQL URL
```

### Pre-Deployment Checklist
- [ ] Change `SECRET_KEY` to a secure random string
- [ ] Update email credentials if needed
- [ ] Test email functionality
- [ ] Verify database connectivity
- [ ] Test user registration/approval flow
- [ ] Check all scraper functionality