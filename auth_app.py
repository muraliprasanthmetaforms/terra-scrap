#!/usr/bin/env python3
"""
Terra Scrap - Multi-Website Scraping Platform with Authentication
A Flask-based web scraping application with user authentication and email verification
"""

from flask import Flask, render_template_string, request, Response, send_file, jsonify, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_mail import Mail, Message
from werkzeug.security import generate_password_hash, check_password_hash
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Email, Length, EqualTo
import threading, queue, time, random, os, csv, re, io, secrets, uuid
import requests
from bs4 import BeautifulSoup, NavigableString, Tag
from urllib.parse import urljoin
from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from datetime import datetime, timedelta

app = Flask(__name__)
app.config['SECRET_KEY'] = 'terra-scrap-secret-key-change-in-production'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///terra_scrap.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Email configuration
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'rgsiddhu5252@gmail.com'
app.config['MAIL_PASSWORD'] = 'miblzeeoegkhtnbq'
app.config['MAIL_DEFAULT_SENDER'] = 'rgsiddhu5252@gmail.com'

# Initialize extensions
db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please login to access Terra Scrap.'
login_manager.login_message_category = 'info'
mail = Mail(app)

# Global state for scrapers
event_queues = {}
scraper_threads = {}
scraper_stop_flags = {}

# User Model
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    is_approved = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    approval_token = db.Column(db.String(100), unique=True)
    reset_token = db.Column(db.String(100), unique=True)
    reset_token_expires = db.Column(db.DateTime)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def generate_approval_token(self):
        self.approval_token = str(uuid.uuid4())
        return self.approval_token
    
    def generate_reset_token(self):
        self.reset_token = str(uuid.uuid4())
        self.reset_token_expires = datetime.utcnow() + timedelta(hours=24)
        return self.reset_token

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Forms
class SignupForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=20)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    password2 = PasswordField('Confirm Password', 
                             validators=[DataRequired(), EqualTo('password', message='Passwords must match')])
    submit = SubmitField('Sign Up')

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Sign In')

class ForgotPasswordForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    submit = SubmitField('Reset Password')

class ResetPasswordForm(FlaskForm):
    password = PasswordField('New Password', validators=[DataRequired(), Length(min=6)])
    password2 = PasswordField('Confirm Password', 
                             validators=[DataRequired(), EqualTo('password', message='Passwords must match')])
    submit = SubmitField('Reset Password')

# Email functions
def send_approval_request_email(user):
    """Send email to admin for user approval"""
    msg = Message(
        subject='Terra Scrap - New User Registration Request',
        recipients=['rgsiddhu5252@gmail.com'],
        html=render_template_string(APPROVAL_EMAIL_TEMPLATE, user=user)
    )
    mail.send(msg)

def send_approval_confirmation_email(user):
    """Send confirmation email to user when approved"""
    msg = Message(
        subject='Terra Scrap - Account Approved!',
        recipients=[user.email],
        html=render_template_string(APPROVAL_CONFIRMATION_TEMPLATE, user=user)
    )
    mail.send(msg)

def send_password_reset_email(user):
    """Send password reset email"""
    msg = Message(
        subject='Terra Scrap - Password Reset Request',
        recipients=[user.email],
        html=render_template_string(RESET_EMAIL_TEMPLATE, user=user)
    )
    mail.send(msg)

# Import scraper classes from previous implementation
class BaseScraper(ABC):
    """Abstract base class for all scrapers"""
    
    def __init__(self):
        self.headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                                     "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"}
        self.delay_min = 0.4
        self.delay_max = 1.0
        self.request_timeout = 18
        self.email_re = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}", re.I)
        self.honorific_re = re.compile(r"\b(Dr|Dr\.|Mr|Mrs|Ms|Miss|Mister|Herr|Frau|Professor|Prof\.?)\b", re.I)
        self.titlecase_name_re = re.compile(r"^[A-ZÄÖÜ][a-zäöüß]+(?:[ \-][A-ZÄÖÜ][a-zäöüß]+)+$")
        
        # Run-local state (cleared at start of each run)
        self.run_total_rows = 0
        self.run_seen_emails = {}
        
        # Cumulative state
        self.seen_emails_freq = {}
        self.total_rows_cumulative = 0
    
    @abstractmethod
    def get_name(self) -> str:
        """Return the display name of the scraper"""
        pass
    
    @abstractmethod
    def get_description(self) -> str:
        """Return a description of what this scraper does"""
        pass
    
    @abstractmethod
    def get_base_url(self) -> str:
        """Return the base URL for the scraper"""
        pass
    
    @abstractmethod
    def get_csv_filename(self) -> str:
        """Return the filename for CSV output"""
        pass
    
    @abstractmethod
    def parse_listing_page(self, html: str, base_url: str) -> List[Dict]:
        """Parse a listing page and return job listings"""
        pass
    
    @abstractmethod
    def extract_detail_fields(self, html: str) -> tuple:
        """Extract detailed fields from a job page"""
        pass
    
    def clean_text(self, s):
        if not s:
            return "N/A"
        s = s.replace("\xa0", " ")
        s = re.sub(r"\s+", " ", s).strip()
        return s if s else "N/A"
    
    def request_get(self, url, retries=3, event_queue=None):
        for attempt in range(retries):
            try:
                r = requests.get(url, headers=self.headers, timeout=self.request_timeout)
                r.raise_for_status()
                if not r.encoding:
                    r.encoding = "utf-8"
                return r.text
            except Exception as e:
                if event_queue:
                    event_queue.put({"type":"log","msg":f"Request error for {url}: {e} — retry {attempt+1}/{retries}"})
                time.sleep(1 + attempt)
        # final try (raise if fails)
        r = requests.get(url, headers=self.headers, timeout=self.request_timeout)
        r.raise_for_status()
        return r.text
    
    def ensure_csv_header(self, path):
        if not os.path.exists(path):
            with open(path, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["Job Title","Company","Contact Name","Email","Job URL","Reference Number","Workplace","Type of job offer","Type of employment contract","Online since","Website","Source Page","Index"])
                f.flush()
    
    def append_row_and_sync(self, path, row):
        with open(path, "a", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(row)
            f.flush()
            try:
                os.fsync(f.fileno())
            except Exception:
                pass
    
    def load_existing_csv_state(self, csv_path, event_queue=None):
        self.seen_emails_freq.clear()
        self.total_rows_cumulative = 0
        if not os.path.exists(csv_path):
            return
        with open(csv_path, newline='', encoding='utf-8') as f:
            r = csv.reader(f)
            header = next(r, None)
            for row in r:
                self.total_rows_cumulative += 1
                if len(row) > 3:
                    email = row[3].strip()
                    if email and email.upper() != "N/A" and self.email_re.match(email):
                        self.seen_emails_freq[email] = self.seen_emails_freq.get(email, 0) + 1
        if event_queue:
            event_queue.put({"type":"log","msg":f"Loaded existing CSV: {self.total_rows_cumulative} rows, {len(self.seen_emails_freq)} unique emails (cumulative)."})

class MakeItGermanyScraper(BaseScraper):
    """Scraper for Make-it-in-Germany job listings"""
    
    def get_name(self):
        return "Make-it-in-Germany"
    
    def get_description(self):
        return "Scrapes job listings from Make-it-in-Germany.com - Official portal for international professionals"
    
    def get_base_url(self):
        return "https://www.make-it-in-germany.com/en/working-in-germany/job-listings?page="
    
    def get_csv_filename(self):
        return "make_it_germany_jobs.csv"
    
    def parse_listing_page(self, html: str, base_url: str) -> List[Dict]:
        soup = BeautifulSoup(html, "lxml")
        jobs = []
        for art in soup.select("li.list__item article"):
            h3 = art.select_one("h3")
            p = art.select_one("p")
            a = art.select_one("a.btn")
            title = self.clean_text(h3.get_text()) if h3 else "N/A"
            company = self.clean_text(p.get_text()) if p else "N/A"
            url = urljoin(base_url, a["href"]) if a and a.has_attr("href") else "N/A"
            jobs.append({"title": title, "company": company, "job_url": url})
        return jobs
    
    def find_value_after_label(self, node, max_steps=20):
        start = node.parent if isinstance(node, NavigableString) else node
        steps = 0
        for sib in start.next_siblings:
            if steps >= max_steps: break
            steps += 1
            if isinstance(sib, NavigableString):
                t = sib.strip()
                if t:
                    return t
                continue
            if isinstance(sib, Tag):
                txt = sib.get_text(" ", strip=True)
                if txt:
                    return txt
        steps = 0
        for el in start.next_elements:
            if steps >= max_steps: break
            steps += 1
            if isinstance(el, NavigableString):
                t = el.strip()
                if t:
                    return t
            elif isinstance(el, Tag):
                txt = el.get_text(" ", strip=True)
                if txt:
                    return txt
        return None
    
    def find_label_value_html(self, soup, label_patterns, company_hint=None):
        for patt in label_patterns:
            for node in soup.find_all(string=re.compile(patt, re.I)):
                val = self.find_value_after_label(node)
                if val:
                    val = val.strip()
                    if val and "http" not in val.lower():
                        return self.clean_text(val)
        for patt in label_patterns:
            for tag in soup.find_all(['strong','b','label','h3','h4','p','div','li'], string=re.compile(patt, re.I)):
                val = self.find_value_after_label(tag)
                if val:
                    val = val.strip()
                    if val and "http" not in val.lower():
                        return self.clean_text(val)
        for patt in label_patterns:
            for tag in soup.find_all(['p','div','li','span','td'], string=re.compile(patt + r".*", re.I)):
                text = tag.get_text(" ", strip=True)
                if ":" in text:
                    parts = text.split(":",1)
                    if len(parts) > 1:
                        return self.clean_text(parts[1])
        return None
    
    def extract_contact_dom(self, soup):
        aside = soup.find("aside")
        search_labels = [r"Contact person", r"Contact person:", r"Contact:", r"Kontakt", r"Kontaktperson", r"Questions and applications to", r"Questions and applications"]
        if aside:
            val = self.find_label_value_html(aside, search_labels)
            if val and val.strip():
                return val
        val = self.find_label_value_html(soup, search_labels)
        if val and val.strip():
            return val
        best = (0, "")
        for t in soup.find_all(string=True):
            txt = t.strip()
            if not txt or len(txt) < 2: continue
            if re.search(r"@|http|www\.|\+?\d{2,}", txt): continue
            score = 0
            if self.honorific_re.search(txt): score = 3
            elif self.titlecase_name_re.match(txt): score = 2
            elif re.match(r"^[A-ZÄÖÜ][a-zäöüß]+ [A-ZÄÖÜ][a-zäöüß]+$", txt): score = 1
            if score > best[0]:
                best = (score, txt)
        if best[0] > 0:
            return self.clean_text(best[1])
        return "N/A"
    
    def extract_detail_fields(self, html: str) -> tuple:
        soup = BeautifulSoup(html, "lxml")
        email = "N/A"
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if href.lower().startswith("mailto:"):
                cand = href.split("mailto:")[-1].split("?")[0].strip()
                if self.email_re.match(cand):
                    email = cand
                    break
        if email == "N/A":
            m = self.email_re.search(soup.get_text(" ", strip=True))
            if m:
                email = m.group(0)
        contact = self.extract_contact_dom(soup)
        refnum = self.find_label_value_html(soup, [r"Reference number", r"Reference no", r"Reference"]) or "N/A"
        workplace = self.find_label_value_html(soup, [r"Workplace"]) or "N/A"
        job_offer_type = self.find_label_value_html(soup, [r"Type of job offer", r"Type of job"]) or "N/A"
        employment_contract = self.find_label_value_html(soup, [r"Type of employment contract", r"Type of employment"]) or "N/A"
        online_since = self.find_label_value_html(soup, [r"Online since"]) or "N/A"
        website = "N/A"
        aside = soup.find("aside")
        if aside:
            for a in aside.find_all("a", href=True):
                href = a["href"].strip()
                if href.lower().startswith("http") and not href.lower().startswith("mailto:"):
                    website = href
                    break
        if website == "N/A":
            anchors = [a["href"].strip() for a in soup.find_all("a", href=True) if a["href"].strip().lower().startswith("http")]
            if anchors:
                website = anchors[-1]
        return contact, email, refnum, workplace, job_offer_type, employment_contract, online_since, website

# Registry of available scrapers
SCRAPERS = {
    'make-it-germany': MakeItGermanyScraper()
}

def get_scraper(scraper_id: str) -> Optional[BaseScraper]:
    return SCRAPERS.get(scraper_id)

def scraper_worker(scraper_id: str, start_page: int, end_page: int):
    """Worker function that runs the scraping process"""
    scraper = get_scraper(scraper_id)
    if not scraper:
        return
    
    event_queue = event_queues.get(scraper_id)
    stop_flag = scraper_stop_flags.get(scraper_id)
    
    if not event_queue or not stop_flag:
        return
    
    csv_path = scraper.get_csv_filename()
    scraper.ensure_csv_header(csv_path)
    
    # Reset run-local state
    scraper.run_total_rows = 0
    scraper.run_seen_emails = {}
    
    # Load existing CSV state
    scraper.load_existing_csv_state(csv_path, event_queue)
    
    base_url = scraper.get_base_url()
    
    for page in range(start_page, end_page + 1):
        if stop_flag.is_set():
            event_queue.put({"type":"log","msg":"Scraper stopped by user."})
            break
        
        listing_url = base_url + str(page)
        event_queue.put({"type":"log","msg":f"Loading listing page {page}..."})
        
        try:
            listing_html = scraper.request_get(listing_url, event_queue=event_queue)
        except Exception as e:
            event_queue.put({"type":"log","msg":f"Failed to load listing page {page}: {e}"})
            continue
        
        jobs = scraper.parse_listing_page(listing_html, listing_url)
        event_queue.put({"type":"log","msg":f"Found {len(jobs)} jobs on page {page}"})
        
        for idx, job in enumerate(jobs, start=1):
            if stop_flag.is_set():
                break
            
            title = job.get("title","N/A")
            company = job.get("company","N/A")
            job_url = job.get("job_url","N/A")
            contact = "N/A"; email = "N/A"
            refnum = workplace = job_offer_type = employment_contract = online_since = website = "N/A"
            
            if job_url != "N/A":
                try:
                    detail_html = scraper.request_get(job_url, event_queue=event_queue)
                    contact, email, refnum, workplace, job_offer_type, employment_contract, online_since, website = scraper.extract_detail_fields(detail_html)
                except Exception as e:
                    event_queue.put({"type":"log","msg":f"Detail fetch failed for {job_url}: {e}"})
            
            # Update counters
            scraper.run_total_rows += 1
            scraper.total_rows_cumulative += 1
            
            email_norm = (email or "").strip()
            if email_norm and email_norm.upper() != "N/A" and scraper.email_re.match(email_norm):
                scraper.run_seen_emails[email_norm] = scraper.run_seen_emails.get(email_norm, 0) + 1
                scraper.seen_emails_freq[email_norm] = scraper.seen_emails_freq.get(email_norm, 0) + 1
            
            # Append to CSV
            row = [title, company, contact, email, job_url, refnum, workplace, job_offer_type, employment_contract, online_since, website, page, idx]
            scraper.append_row_and_sync(csv_path, row)
            
            # Emit row and summary
            event_queue.put({"type":"row","row":row})
            unique_count_run = len(scraper.run_seen_emails)
            total_emails_run = sum(scraper.run_seen_emails.values())
            duplicate_count_run = max(0, total_emails_run - unique_count_run)
            event_queue.put({"type":"summary","total": scraper.run_total_rows, "unique": unique_count_run, "duplicate": duplicate_count_run})
            
            time.sleep(scraper.delay_min + random.random() * (scraper.delay_max - scraper.delay_min))
    
    event_queue.put({"type":"done","total": scraper.run_total_rows})

# Utility functions for CSV operations
def generate_unique_csv(csv_path):
    if not os.path.exists(csv_path):
        return None
    seen = set()
    out = io.StringIO()
    w = csv.writer(out)
    email_re = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}", re.I)
    with open(csv_path, newline='', encoding='utf-8') as f:
        r = csv.reader(f)
        header = next(r, None)
        if header:
            w.writerow(header)
        for row in r:
            if len(row) < 4: continue
            email = row[3].strip()
            if email and email.upper() != "N/A" and email_re.match(email) and email not in seen:
                seen.add(email)
                w.writerow(row)
    out.seek(0)
    return out

def generate_duplicates_csv(csv_path):
    if not os.path.exists(csv_path):
        return None
    freq = {}
    rows_by_email = {}
    with open(csv_path, newline='', encoding='utf-8') as f:
        r = csv.reader(f)
        header = next(r, None)
        for row in r:
            if len(row) < 4: continue
            email = row[3].strip()
            if not email or email.upper() == "N/A": continue
            freq[email] = freq.get(email, 0) + 1
            rows_by_email.setdefault(email, []).append(row)
    out = io.StringIO()
    w = csv.writer(out)
    if header:
        w.writerow(header)
    for e, count in freq.items():
        if count > 1:
            for row in rows_by_email[e]:
                w.writerow(row)
    out.seek(0)
    return out

# Authentication Routes
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    
    form = LoginForm()
    if form.validate_on_submit():
        # Try to find user by username or email
        user = User.query.filter_by(username=form.username.data).first()
        if not user:
            user = User.query.filter_by(email=form.username.data).first()
        if user and user.check_password(form.password.data):
            if user.is_approved:
                login_user(user)
                flash('Welcome back!', 'success')
                next_page = request.args.get('next')
                return redirect(next_page) if next_page else redirect(url_for('home'))
            else:
                flash('Your account is pending approval. Please wait for admin approval.', 'warning')
        else:
            flash('Invalid username or password', 'error')
    
    return render_template_string(LOGIN_HTML, form=form)

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    
    form = SignupForm()
    if form.validate_on_submit():
        # Check if user already exists
        if User.query.filter_by(username=form.username.data).first():
            flash('Username already exists', 'error')
            return render_template_string(SIGNUP_HTML, form=form)
        
        if User.query.filter_by(email=form.email.data).first():
            flash('Email already registered', 'error')
            return render_template_string(SIGNUP_HTML, form=form)
        
        # Create new user
        user = User(
            username=form.username.data,
            email=form.email.data
        )
        user.set_password(form.password.data)
        user.generate_approval_token()
        
        db.session.add(user)
        db.session.commit()
        
        # Send approval email
        try:
            send_approval_request_email(user)
            flash('Registration successful! An approval request has been sent to the administrator. You will receive an email once your account is approved.', 'success')
        except Exception as e:
            flash('Registration successful but failed to send approval email. Please contact administrator.', 'warning')
        
        return redirect(url_for('login'))
    
    return render_template_string(SIGNUP_HTML, form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    
    form = ForgotPasswordForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user:
            user.generate_reset_token()
            db.session.commit()
            try:
                send_password_reset_email(user)
                flash('Password reset email sent! Check your inbox.', 'success')
            except Exception as e:
                flash('Failed to send reset email. Please try again later.', 'error')
        else:
            flash('Password reset email sent! Check your inbox.', 'success')  # Don't reveal if email exists
        
        return redirect(url_for('login'))
    
    return render_template_string(FORGOT_PASSWORD_HTML, form=form)

@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    
    user = User.query.filter_by(reset_token=token).first()
    if not user or not user.reset_token_expires or user.reset_token_expires < datetime.utcnow():
        flash('Invalid or expired reset link', 'error')
        return redirect(url_for('forgot_password'))
    
    form = ResetPasswordForm()
    if form.validate_on_submit():
        user.set_password(form.password.data)
        user.reset_token = None
        user.reset_token_expires = None
        db.session.commit()
        flash('Your password has been reset successfully!', 'success')
        return redirect(url_for('login'))
    
    return render_template_string(RESET_PASSWORD_HTML, form=form)

@app.route('/approve-user/<token>')
def approve_user(token):
    user = User.query.filter_by(approval_token=token).first()
    if not user:
        return "Invalid approval link", 404
    
    user.is_approved = True
    user.approval_token = None
    db.session.commit()
    
    # Send confirmation email to user
    try:
        send_approval_confirmation_email(user)
    except Exception as e:
        pass
    
    return render_template_string(APPROVAL_SUCCESS_HTML, user=user)

@app.route('/reject-user/<token>')
def reject_user(token):
    user = User.query.filter_by(approval_token=token).first()
    if not user:
        return "Invalid approval link", 404
    
    # Delete the user
    db.session.delete(user)
    db.session.commit()
    
    return render_template_string(REJECTION_SUCCESS_HTML, user=user)

# Protected Routes
@app.route('/')
@login_required
def home():
    """Home page showing list of available scrapers"""
    return render_template_string(HOME_HTML, scrapers=SCRAPERS, user=current_user)

@app.route('/scraper/<scraper_id>')
@login_required
def scraper_page(scraper_id):
    """Individual scraper page"""
    scraper = get_scraper(scraper_id)
    if not scraper:
        return "Scraper not found", 404
    return render_template_string(SCRAPER_HTML, scraper=scraper, scraper_id=scraper_id, user=current_user)

@app.route('/start_scrape/<scraper_id>', methods=['POST'])
@login_required
def start_scrape(scraper_id):
    global scraper_threads
    scraper = get_scraper(scraper_id)
    if not scraper:
        return jsonify({"status": "scraper_not_found"}), 404
    
    data = request.get_json(force=True)
    start = int(data.get('start', 1))
    end = int(data.get('end', 1))
    
    # Check if scraper is already running
    thread = scraper_threads.get(scraper_id)
    if thread and thread.is_alive():
        return jsonify({"status":"already_running"}), 400
    
    # Initialize event queue and stop flag for this scraper
    event_queues[scraper_id] = queue.Queue()
    scraper_stop_flags[scraper_id] = threading.Event()
    
    # Reset UI
    event_queues[scraper_id].put({"type":"reset"})
    
    # Start scraper thread
    scraper_stop_flags[scraper_id].clear()
    scraper_threads[scraper_id] = threading.Thread(
        target=scraper_worker, 
        args=(scraper_id, start, end), 
        daemon=True
    )
    scraper_threads[scraper_id].start()
    
    return jsonify({"status":"started","start":start,"end":end})

@app.route('/stop_scrape/<scraper_id>', methods=['POST'])
@login_required
def stop_scrape(scraper_id):
    stop_flag = scraper_stop_flags.get(scraper_id)
    if stop_flag:
        stop_flag.set()
    return jsonify({"status":"stopping"})

@app.route('/events/<scraper_id>')
@login_required
def sse_events(scraper_id):
    def gen():
        event_queue = event_queues.get(scraper_id)
        thread = scraper_threads.get(scraper_id)
        if not event_queue:
            return
        
        while True:
            try:
                item = event_queue.get(timeout=0.5)
            except queue.Empty:
                if not (thread and thread.is_alive()) and event_queue.empty():
                    break
                continue
            import json
            yield f"data: {json.dumps(item)}\n\n"
            if item.get("type") == "done":
                break
    return Response(gen(), mimetype='text/event-stream')

@app.route('/download/<scraper_id>')
@login_required
def download(scraper_id):
    scraper = get_scraper(scraper_id)
    if not scraper:
        return "Scraper not found", 404
    
    csv_path = scraper.get_csv_filename()
    if not os.path.exists(csv_path):
        return "No CSV yet", 404
    return send_file(csv_path, as_attachment=True)

@app.route('/download_unique/<scraper_id>')
@login_required
def download_unique(scraper_id):
    scraper = get_scraper(scraper_id)
    if not scraper:
        return "Scraper not found", 404
    
    csv_path = scraper.get_csv_filename()
    out = generate_unique_csv(csv_path)
    if not out:
        return "No CSV yet", 404
    return Response(out.getvalue(), mimetype='text/csv', 
                   headers={"Content-disposition":"attachment; filename=unique_emails.csv"})

@app.route('/download_duplicates/<scraper_id>')
@login_required
def download_duplicates(scraper_id):
    scraper = get_scraper(scraper_id)
    if not scraper:
        return "Scraper not found", 404
    
    csv_path = scraper.get_csv_filename()
    out = generate_duplicates_csv(csv_path)
    if not out:
        return "No CSV yet", 404
    return Response(out.getvalue(), mimetype='text/csv', 
                   headers={"Content-disposition":"attachment; filename=duplicate_emails.csv"})

@app.route('/debug')
def debug_route():
    """Debug route for production troubleshooting - REMOVE IN PRODUCTION"""
    import os
    import sys
    from datetime import datetime
    
    try:
        info = {
            "timestamp": datetime.utcnow().isoformat(),
            "environment": {
                "SECRET_KEY_SET": bool(os.environ.get('SECRET_KEY')),
                "SECRET_KEY_LENGTH": len(os.environ.get('SECRET_KEY', '')),
                "MAIL_USERNAME": os.environ.get('MAIL_USERNAME', 'NOT_SET'),
                "MAIL_PASSWORD_SET": bool(os.environ.get('MAIL_PASSWORD')),
                "PORT": os.environ.get('PORT', 'NOT_SET'),
                "FLASK_ENV": os.environ.get('FLASK_ENV', 'NOT_SET'),
            },
            "flask_config": {
                "SECRET_KEY_SET": bool(app.config.get('SECRET_KEY')),
                "MAIL_SERVER": app.config.get('MAIL_SERVER'),
                "MAIL_PORT": app.config.get('MAIL_PORT'),
                "MAIL_USE_TLS": app.config.get('MAIL_USE_TLS'),
                "MAIL_USERNAME": app.config.get('MAIL_USERNAME'),
                "DATABASE_URI": app.config.get('SQLALCHEMY_DATABASE_URI'),
            },
            "python_info": {
                "version": sys.version,
                "platform": sys.platform,
            }
        }
        
        # Test database
        try:
            user_count = User.query.count()
            users = User.query.all()
            info["database"] = {
                "status": "connected",
                "user_count": user_count,
                "users": [{"id": u.id, "username": u.username, "email": u.email, "approved": u.is_approved} for u in users],
                "url": app.config.get('SQLALCHEMY_DATABASE_URI'),
            }
        except Exception as e:
            info["database"] = {
                "status": "error",
                "error": str(e),
            }
        
        return jsonify(info)
    except Exception as e:
        return jsonify({"error": str(e), "type": "debug_route_error"})

# HTML Templates
LOGIN_HTML = """
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>Sign In - Terra Scrap</title>
<style>
:root{
  --bg:#0a0e1a;
  --card:#0f1a2b;
  --muted:#a8cbd6;
  --accent:#f2d100;
  --accent2:#dd1818;
  --teal:#47c8d8;
  --purple:#8b5cf6;
}
body{
  font-family:Inter, system-ui, -apple-system, "Segoe UI", Roboto, Arial; 
  background:linear-gradient(180deg,var(--bg),#0e1726); 
  color:#e8f7f8; 
  margin:0;
  padding:28px;
  min-height:100vh;
  display: flex;
  align-items: center;
  justify-content: center;
}
.auth-container{
  max-width: 400px;
  width: 100%;
}
.auth-card{
  background:linear-gradient(180deg,var(--card),#0a1420); 
  padding:40px;
  border-radius:16px;
  box-shadow:0 12px 40px rgba(0,0,0,0.6);
  border: 1px solid rgba(255,255,255,0.05);
  text-align: center;
}
.logo{
  font-size: 36px;
  background: linear-gradient(135deg, var(--teal), var(--purple));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  margin-bottom: 10px;
}
.subtitle{
  color: var(--muted);
  margin-bottom: 30px;
}
.form-group{
  margin-bottom: 20px;
  text-align: left;
}
.form-group label{
  display: block;
  margin-bottom: 5px;
  color: var(--muted);
  font-weight: 500;
}
.form-control{
  width: 100%;
  background: #05282f;
  border: 1px solid rgba(255,255,255,0.1);
  padding: 12px;
  border-radius: 8px;
  color: #dff7f9;
  font-size: 14px;
  box-sizing: border-box;
}
.form-control:focus{
  outline: none;
  border-color: var(--teal);
  box-shadow: 0 0 0 2px rgba(71, 200, 216, 0.1);
}
.btn{
  background: linear-gradient(135deg, var(--teal), var(--purple));
  color: white;
  border: none;
  padding: 12px 24px;
  border-radius: 10px;
  cursor: pointer;
  font-weight: 600;
  width: 100%;
  font-size: 16px;
  transition: all 0.2s ease;
  margin-bottom: 20px;
}
.btn:hover{
  transform: scale(1.02);
  box-shadow: 0 8px 20px rgba(71, 200, 216, 0.3);
}
.auth-links{
  text-align: center;
  margin-top: 20px;
}
.auth-links a{
  color: var(--teal);
  text-decoration: none;
  margin: 0 10px;
}
.auth-links a:hover{
  text-decoration: underline;
}
.flash-messages{
  margin-bottom: 20px;
}
.flash-message{
  padding: 10px;
  border-radius: 8px;
  margin-bottom: 10px;
}
.flash-success{
  background: rgba(16, 185, 129, 0.1);
  border: 1px solid rgba(16, 185, 129, 0.3);
  color: #10b981;
}
.flash-error{
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3);
  color: #ef4444;
}
.flash-warning{
  background: rgba(245, 158, 11, 0.1);
  border: 1px solid rgba(245, 158, 11, 0.3);
  color: #f59e0b;
}
.flash-info{
  background: rgba(59, 130, 246, 0.1);
  border: 1px solid rgba(59, 130, 246, 0.3);
  color: #3b82f6;
}
</style>
</head>
<body>
<div class="auth-container">
  <div class="auth-card">
    <div class="logo">🌍 Terra Scrap</div>
    <div class="subtitle">Sign in to your account</div>
    
    {% with messages = get_flashed_messages(with_categories=true) %}
      {% if messages %}
        <div class="flash-messages">
          {% for category, message in messages %}
            <div class="flash-message flash-{{ category }}">{{ message }}</div>
          {% endfor %}
        </div>
      {% endif %}
    {% endwith %}
    
    <form method="POST">
      {{ form.hidden_tag() }}
      <div class="form-group">
        {{ form.username.label(class="form-label") }}
        {{ form.username(class="form-control") }}
      </div>
      <div class="form-group">
        {{ form.password.label(class="form-label") }}
        {{ form.password(class="form-control") }}
      </div>
      {{ form.submit(class="btn") }}
    </form>
    
    <div class="auth-links">
      <a href="{{ url_for('signup') }}">Create Account</a>
      <a href="{{ url_for('forgot_password') }}">Forgot Password?</a>
    </div>
  </div>
</div>
</body>
</html>
"""

SIGNUP_HTML = """
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>Sign Up - Terra Scrap</title>
<style>
:root{
  --bg:#0a0e1a;
  --card:#0f1a2b;
  --muted:#a8cbd6;
  --accent:#f2d100;
  --accent2:#dd1818;
  --teal:#47c8d8;
  --purple:#8b5cf6;
}
body{
  font-family:Inter, system-ui, -apple-system, "Segoe UI", Roboto, Arial; 
  background:linear-gradient(180deg,var(--bg),#0e1726); 
  color:#e8f7f8; 
  margin:0;
  padding:28px;
  min-height:100vh;
  display: flex;
  align-items: center;
  justify-content: center;
}
.auth-container{
  max-width: 400px;
  width: 100%;
}
.auth-card{
  background:linear-gradient(180deg,var(--card),#0a1420); 
  padding:40px;
  border-radius:16px;
  box-shadow:0 12px 40px rgba(0,0,0,0.6);
  border: 1px solid rgba(255,255,255,0.05);
  text-align: center;
}
.logo{
  font-size: 36px;
  background: linear-gradient(135deg, var(--teal), var(--purple));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  margin-bottom: 10px;
}
.subtitle{
  color: var(--muted);
  margin-bottom: 30px;
}
.form-group{
  margin-bottom: 20px;
  text-align: left;
}
.form-group label{
  display: block;
  margin-bottom: 5px;
  color: var(--muted);
  font-weight: 500;
}
.form-control{
  width: 100%;
  background: #05282f;
  border: 1px solid rgba(255,255,255,0.1);
  padding: 12px;
  border-radius: 8px;
  color: #dff7f9;
  font-size: 14px;
  box-sizing: border-box;
}
.form-control:focus{
  outline: none;
  border-color: var(--teal);
  box-shadow: 0 0 0 2px rgba(71, 200, 216, 0.1);
}
.btn{
  background: linear-gradient(135deg, var(--teal), var(--purple));
  color: white;
  border: none;
  padding: 12px 24px;
  border-radius: 10px;
  cursor: pointer;
  font-weight: 600;
  width: 100%;
  font-size: 16px;
  transition: all 0.2s ease;
  margin-bottom: 20px;
}
.btn:hover{
  transform: scale(1.02);
  box-shadow: 0 8px 20px rgba(71, 200, 216, 0.3);
}
.auth-links{
  text-align: center;
  margin-top: 20px;
}
.auth-links a{
  color: var(--teal);
  text-decoration: none;
}
.auth-links a:hover{
  text-decoration: underline;
}
.flash-messages{
  margin-bottom: 20px;
}
.flash-message{
  padding: 10px;
  border-radius: 8px;
  margin-bottom: 10px;
}
.flash-success{
  background: rgba(16, 185, 129, 0.1);
  border: 1px solid rgba(16, 185, 129, 0.3);
  color: #10b981;
}
.flash-error{
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3);
  color: #ef4444;
}
.flash-warning{
  background: rgba(245, 158, 11, 0.1);
  border: 1px solid rgba(245, 158, 11, 0.3);
  color: #f59e0b;
}
</style>
</head>
<body>
<div class="auth-container">
  <div class="auth-card">
    <div class="logo">🌍 Terra Scrap</div>
    <div class="subtitle">Create your account</div>
    
    {% with messages = get_flashed_messages(with_categories=true) %}
      {% if messages %}
        <div class="flash-messages">
          {% for category, message in messages %}
            <div class="flash-message flash-{{ category }}">{{ message }}</div>
          {% endfor %}
        </div>
      {% endif %}
    {% endwith %}
    
    <form method="POST">
      {{ form.hidden_tag() }}
      <div class="form-group">
        {{ form.username.label(class="form-label") }}
        {{ form.username(class="form-control") }}
      </div>
      <div class="form-group">
        {{ form.email.label(class="form-label") }}
        {{ form.email(class="form-control") }}
      </div>
      <div class="form-group">
        {{ form.password.label(class="form-label") }}
        {{ form.password(class="form-control") }}
      </div>
      <div class="form-group">
        {{ form.password2.label(class="form-label") }}
        {{ form.password2(class="form-control") }}
      </div>
      {{ form.submit(class="btn") }}
    </form>
    
    <div class="auth-links">
      <a href="{{ url_for('login') }}">Already have an account? Sign In</a>
    </div>
  </div>
</div>
</body>
</html>
"""

FORGOT_PASSWORD_HTML = """
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>Forgot Password - Terra Scrap</title>
<style>
:root{
  --bg:#0a0e1a;
  --card:#0f1a2b;
  --muted:#a8cbd6;
  --accent:#f2d100;
  --accent2:#dd1818;
  --teal:#47c8d8;
  --purple:#8b5cf6;
}
body{
  font-family:Inter, system-ui, -apple-system, "Segoe UI", Roboto, Arial; 
  background:linear-gradient(180deg,var(--bg),#0e1726); 
  color:#e8f7f8; 
  margin:0;
  padding:28px;
  min-height:100vh;
  display: flex;
  align-items: center;
  justify-content: center;
}
.auth-container{
  max-width: 400px;
  width: 100%;
}
.auth-card{
  background:linear-gradient(180deg,var(--card),#0a1420); 
  padding:40px;
  border-radius:16px;
  box-shadow:0 12px 40px rgba(0,0,0,0.6);
  border: 1px solid rgba(255,255,255,0.05);
  text-align: center;
}
.logo{
  font-size: 36px;
  background: linear-gradient(135deg, var(--teal), var(--purple));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  margin-bottom: 10px;
}
.subtitle{
  color: var(--muted);
  margin-bottom: 30px;
}
.form-group{
  margin-bottom: 20px;
  text-align: left;
}
.form-group label{
  display: block;
  margin-bottom: 5px;
  color: var(--muted);
  font-weight: 500;
}
.form-control{
  width: 100%;
  background: #05282f;
  border: 1px solid rgba(255,255,255,0.1);
  padding: 12px;
  border-radius: 8px;
  color: #dff7f9;
  font-size: 14px;
  box-sizing: border-box;
}
.form-control:focus{
  outline: none;
  border-color: var(--teal);
  box-shadow: 0 0 0 2px rgba(71, 200, 216, 0.1);
}
.btn{
  background: linear-gradient(135deg, var(--teal), var(--purple));
  color: white;
  border: none;
  padding: 12px 24px;
  border-radius: 10px;
  cursor: pointer;
  font-weight: 600;
  width: 100%;
  font-size: 16px;
  transition: all 0.2s ease;
  margin-bottom: 20px;
}
.btn:hover{
  transform: scale(1.02);
  box-shadow: 0 8px 20px rgba(71, 200, 216, 0.3);
}
.auth-links{
  text-align: center;
  margin-top: 20px;
}
.auth-links a{
  color: var(--teal);
  text-decoration: none;
}
.auth-links a:hover{
  text-decoration: underline;
}
.flash-messages{
  margin-bottom: 20px;
}
.flash-message{
  padding: 10px;
  border-radius: 8px;
  margin-bottom: 10px;
}
.flash-success{
  background: rgba(16, 185, 129, 0.1);
  border: 1px solid rgba(16, 185, 129, 0.3);
  color: #10b981;
}
.flash-error{
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3);
  color: #ef4444;
}
</style>
</head>
<body>
<div class="auth-container">
  <div class="auth-card">
    <div class="logo">🌍 Terra Scrap</div>
    <div class="subtitle">Reset your password</div>
    
    {% with messages = get_flashed_messages(with_categories=true) %}
      {% if messages %}
        <div class="flash-messages">
          {% for category, message in messages %}
            <div class="flash-message flash-{{ category }}">{{ message }}</div>
          {% endfor %}
        </div>
      {% endif %}
    {% endwith %}
    
    <form method="POST">
      {{ form.hidden_tag() }}
      <div class="form-group">
        {{ form.email.label(class="form-label") }}
        {{ form.email(class="form-control") }}
      </div>
      {{ form.submit(class="btn") }}
    </form>
    
    <div class="auth-links">
      <a href="{{ url_for('login') }}">Back to Sign In</a>
    </div>
  </div>
</div>
</body>
</html>
"""

RESET_PASSWORD_HTML = """
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>Reset Password - Terra Scrap</title>
<style>
:root{
  --bg:#0a0e1a;
  --card:#0f1a2b;
  --muted:#a8cbd6;
  --accent:#f2d100;
  --accent2:#dd1818;
  --teal:#47c8d8;
  --purple:#8b5cf6;
}
body{
  font-family:Inter, system-ui, -apple-system, "Segoe UI", Roboto, Arial; 
  background:linear-gradient(180deg,var(--bg),#0e1726); 
  color:#e8f7f8; 
  margin:0;
  padding:28px;
  min-height:100vh;
  display: flex;
  align-items: center;
  justify-content: center;
}
.auth-container{
  max-width: 400px;
  width: 100%;
}
.auth-card{
  background:linear-gradient(180deg,var(--card),#0a1420); 
  padding:40px;
  border-radius:16px;
  box-shadow:0 12px 40px rgba(0,0,0,0.6);
  border: 1px solid rgba(255,255,255,0.05);
  text-align: center;
}
.logo{
  font-size: 36px;
  background: linear-gradient(135deg, var(--teal), var(--purple));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  margin-bottom: 10px;
}
.subtitle{
  color: var(--muted);
  margin-bottom: 30px;
}
.form-group{
  margin-bottom: 20px;
  text-align: left;
}
.form-group label{
  display: block;
  margin-bottom: 5px;
  color: var(--muted);
  font-weight: 500;
}
.form-control{
  width: 100%;
  background: #05282f;
  border: 1px solid rgba(255,255,255,0.1);
  padding: 12px;
  border-radius: 8px;
  color: #dff7f9;
  font-size: 14px;
  box-sizing: border-box;
}
.form-control:focus{
  outline: none;
  border-color: var(--teal);
  box-shadow: 0 0 0 2px rgba(71, 200, 216, 0.1);
}
.btn{
  background: linear-gradient(135deg, var(--teal), var(--purple));
  color: white;
  border: none;
  padding: 12px 24px;
  border-radius: 10px;
  cursor: pointer;
  font-weight: 600;
  width: 100%;
  font-size: 16px;
  transition: all 0.2s ease;
  margin-bottom: 20px;
}
.btn:hover{
  transform: scale(1.02);
  box-shadow: 0 8px 20px rgba(71, 200, 216, 0.3);
}
.auth-links{
  text-align: center;
  margin-top: 20px;
}
.auth-links a{
  color: var(--teal);
  text-decoration: none;
}
.auth-links a:hover{
  text-decoration: underline;
}
.flash-messages{
  margin-bottom: 20px;
}
.flash-message{
  padding: 10px;
  border-radius: 8px;
  margin-bottom: 10px;
}
.flash-success{
  background: rgba(16, 185, 129, 0.1);
  border: 1px solid rgba(16, 185, 129, 0.3);
  color: #10b981;
}
.flash-error{
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3);
  color: #ef4444;
}
</style>
</head>
<body>
<div class="auth-container">
  <div class="auth-card">
    <div class="logo">🌍 Terra Scrap</div>
    <div class="subtitle">Enter your new password</div>
    
    {% with messages = get_flashed_messages(with_categories=true) %}
      {% if messages %}
        <div class="flash-messages">
          {% for category, message in messages %}
            <div class="flash-message flash-{{ category }}">{{ message }}</div>
          {% endfor %}
        </div>
      {% endif %}
    {% endwith %}
    
    <form method="POST">
      {{ form.hidden_tag() }}
      <div class="form-group">
        {{ form.password.label(class="form-label") }}
        {{ form.password(class="form-control") }}
      </div>
      <div class="form-group">
        {{ form.password2.label(class="form-label") }}
        {{ form.password2(class="form-control") }}
      </div>
      {{ form.submit(class="btn") }}
    </form>
  </div>
</div>
</body>
</html>
"""

# Email Templates
APPROVAL_EMAIL_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>New User Registration - Terra Scrap</title>
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
        .container { max-width: 600px; margin: 0 auto; padding: 20px; }
        .header { background: linear-gradient(135deg, #47c8d8, #8b5cf6); color: white; padding: 20px; text-align: center; border-radius: 10px 10px 0 0; }
        .content { background: #f9f9f9; padding: 20px; }
        .button { display: inline-block; padding: 12px 24px; margin: 10px; border-radius: 6px; text-decoration: none; font-weight: bold; }
        .approve { background: #10b981; color: white; }
        .reject { background: #ef4444; color: white; }
        .user-details { background: white; padding: 15px; border-radius: 6px; margin: 15px 0; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🌍 Terra Scrap</h1>
            <h2>New User Registration Request</h2>
        </div>
        <div class="content">
            <p>A new user has requested access to Terra Scrap:</p>
            
            <div class="user-details">
                <strong>Username:</strong> {{ user.username }}<br>
                <strong>Email:</strong> {{ user.email }}<br>
                <strong>Registration Date:</strong> {{ user.created_at.strftime('%Y-%m-%d %H:%M:%S') }}
            </div>
            
            <p>Please review this request and choose an action:</p>
            
            <div style="text-align: center; margin: 30px 0;">
                <a href="{{ url_for('approve_user', token=user.approval_token, _external=True) }}" class="button approve">
                    ✅ APPROVE USER
                </a>
                <a href="{{ url_for('reject_user', token=user.approval_token, _external=True) }}" class="button reject">
                    ❌ REJECT USER
                </a>
            </div>
            
            <p><em>Note: Approving will allow the user to access Terra Scrap. Rejecting will delete their account.</em></p>
        </div>
    </div>
</body>
</html>
"""

APPROVAL_CONFIRMATION_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Account Approved - Terra Scrap</title>
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
        .container { max-width: 600px; margin: 0 auto; padding: 20px; }
        .header { background: linear-gradient(135deg, #47c8d8, #8b5cf6); color: white; padding: 20px; text-align: center; border-radius: 10px 10px 0 0; }
        .content { background: #f9f9f9; padding: 20px; border-radius: 0 0 10px 10px; }
        .button { display: inline-block; padding: 12px 24px; background: #10b981; color: white; border-radius: 6px; text-decoration: none; font-weight: bold; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🌍 Terra Scrap</h1>
            <h2>Welcome to Terra Scrap!</h2>
        </div>
        <div class="content">
            <p>Hi {{ user.username }},</p>
            
            <p>Great news! Your Terra Scrap account has been approved by our administrator.</p>
            
            <p>You can now sign in and start using our multi-website scraping platform to extract job listings and contact information from various sources.</p>
            
            <div style="text-align: center; margin: 30px 0;">
                <a href="{{ url_for('login', _external=True) }}" class="button">
                    Sign In Now
                </a>
            </div>
            
            <p>If you have any questions or need assistance, please don't hesitate to contact us.</p>
            
            <p>Happy scraping!<br>
            The Terra Scrap Team</p>
        </div>
    </div>
</body>
</html>
"""

RESET_EMAIL_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Password Reset - Terra Scrap</title>
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
        .container { max-width: 600px; margin: 0 auto; padding: 20px; }
        .header { background: linear-gradient(135deg, #47c8d8, #8b5cf6); color: white; padding: 20px; text-align: center; border-radius: 10px 10px 0 0; }
        .content { background: #f9f9f9; padding: 20px; border-radius: 0 0 10px 10px; }
        .button { display: inline-block; padding: 12px 24px; background: #47c8d8; color: white; border-radius: 6px; text-decoration: none; font-weight: bold; }
        .warning { background: #fef3cd; border: 1px solid #fecaca; padding: 10px; border-radius: 6px; margin: 15px 0; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🌍 Terra Scrap</h1>
            <h2>Password Reset Request</h2>
        </div>
        <div class="content">
            <p>Hi {{ user.username }},</p>
            
            <p>We received a request to reset your Terra Scrap password. If you made this request, click the button below to set a new password:</p>
            
            <div style="text-align: center; margin: 30px 0;">
                <a href="{{ url_for('reset_password', token=user.reset_token, _external=True) }}" class="button">
                    Reset Password
                </a>
            </div>
            
            <div class="warning">
                <strong>⚠️ Security Note:</strong> This link will expire in 24 hours. If you didn't request this password reset, please ignore this email.
            </div>
            
            <p>If you have any concerns about your account security, please contact us immediately.</p>
            
            <p>Best regards,<br>
            The Terra Scrap Team</p>
        </div>
    </div>
</body>
</html>
"""

APPROVAL_SUCCESS_HTML = """
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>User Approved - Terra Scrap</title>
<style>
:root{
  --bg:#0a0e1a;
  --card:#0f1a2b;
  --muted:#a8cbd6;
  --teal:#47c8d8;
  --green:#10b981;
}
body{
  font-family:Inter, system-ui, -apple-system, "Segoe UI", Roboto, Arial; 
  background:linear-gradient(180deg,var(--bg),#0e1726); 
  color:#e8f7f8; 
  margin:0;
  padding:28px;
  min-height:100vh;
  display: flex;
  align-items: center;
  justify-content: center;
}
.success-card{
  background:linear-gradient(180deg,var(--card),#0a1420); 
  padding:40px;
  border-radius:16px;
  box-shadow:0 12px 40px rgba(0,0,0,0.6);
  border: 1px solid var(--green);
  text-align: center;
  max-width: 500px;
}
.success-icon{
  font-size: 64px;
  margin-bottom: 20px;
}
.title{
  color: var(--green);
  font-size: 24px;
  margin-bottom: 20px;
}
</style>
</head>
<body>
<div class="success-card">
  <div class="success-icon">✅</div>
  <div class="title">User Approved Successfully!</div>
  <p>The user <strong>{{ user.username }}</strong> ({{ user.email }}) has been approved and can now access Terra Scrap.</p>
  <p>A confirmation email has been sent to the user.</p>
</div>
</body>
</html>
"""

REJECTION_SUCCESS_HTML = """
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>User Rejected - Terra Scrap</title>
<style>
:root{
  --bg:#0a0e1a;
  --card:#0f1a2b;
  --muted:#a8cbd6;
  --teal:#47c8d8;
  --red:#ef4444;
}
body{
  font-family:Inter, system-ui, -apple-system, "Segoe UI", Roboto, Arial; 
  background:linear-gradient(180deg,var(--bg),#0e1726); 
  color:#e8f7f8; 
  margin:0;
  padding:28px;
  min-height:100vh;
  display: flex;
  align-items: center;
  justify-content: center;
}
.rejection-card{
  background:linear-gradient(180deg,var(--card),#0a1420); 
  padding:40px;
  border-radius:16px;
  box-shadow:0 12px 40px rgba(0,0,0,0.6);
  border: 1px solid var(--red);
  text-align: center;
  max-width: 500px;
}
.rejection-icon{
  font-size: 64px;
  margin-bottom: 20px;
}
.title{
  color: var(--red);
  font-size: 24px;
  margin-bottom: 20px;
}
</style>
</head>
<body>
<div class="rejection-card">
  <div class="rejection-icon">❌</div>
  <div class="title">User Registration Rejected</div>
  <p>The registration request from <strong>{{ user.username }}</strong> ({{ user.email }}) has been rejected.</p>
  <p>The user account has been removed from the system.</p>
</div>
</body>
</html>
"""

# Updated Home and Scraper Templates with Authentication
HOME_HTML = """
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>Terra Scrap - Multi-Website Scraping Platform</title>
<style>
:root{
  --bg:#0a0e1a;
  --card:#0f1a2b;
  --muted:#a8cbd6;
  --accent:#f2d100;
  --accent2:#dd1818;
  --teal:#47c8d8;
  --purple:#8b5cf6;
  --green:#10b981;
}
body{
  font-family:Inter, system-ui, -apple-system, "Segoe UI", Roboto, Arial; 
  background:linear-gradient(180deg,var(--bg),#0e1726); 
  color:#e8f7f8; 
  margin:0;
  padding:28px;
  min-height:100vh;
}
.container{max-width:1200px;margin:0 auto}
.top-nav{
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  padding: 15px 20px;
  background: linear-gradient(180deg,var(--card),#0a1420);
  border-radius: 12px;
  border: 1px solid rgba(255,255,255,0.05);
}
.user-info{
  display: flex;
  align-items: center;
  gap: 15px;
  color: var(--muted);
}
.logout-btn{
  background: var(--accent2);
  color: white;
  border: none;
  padding: 8px 16px;
  border-radius: 6px;
  cursor: pointer;
  text-decoration: none;
  font-size: 14px;
}
header{text-align:center;margin-bottom:40px}
h1{
  margin:0 0 10px 0;
  color:var(--teal);
  font-size:42px;
  background: linear-gradient(135deg, var(--teal), var(--purple));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}
.subtitle{color:var(--muted);font-size:18px;margin-bottom:10px}
.description{color:#b0c4d1;max-width:600px;margin:0 auto 40px;line-height:1.6}

.scrapers-grid{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
  gap: 20px;
  margin-top: 30px;
}

.scraper-card{
  background:linear-gradient(180deg,var(--card),#0a1420); 
  padding:24px;
  border-radius:16px;
  box-shadow:0 12px 40px rgba(0,0,0,0.6);
  border: 1px solid rgba(255,255,255,0.05);
  transition: all 0.3s ease;
  cursor: pointer;
  position: relative;
  overflow: hidden;
}

.scraper-card:hover{
  transform: translateY(-5px);
  box-shadow: 0 20px 60px rgba(0,0,0,0.8);
  border-color: var(--teal);
}

.scraper-card::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 3px;
  background: linear-gradient(90deg, var(--teal), var(--purple), var(--green));
}

.scraper-title{
  color: var(--teal);
  font-size: 22px;
  font-weight: 700;
  margin-bottom: 12px;
  display: flex;
  align-items: center;
  gap: 10px;
}

.scraper-description{
  color: var(--muted);
  line-height: 1.5;
  margin-bottom: 20px;
}

.scraper-url{
  color: #7dd3fc;
  font-size: 14px;
  opacity: 0.8;
  margin-bottom: 20px;
  word-break: break-all;
}

.scraper-button{
  background: linear-gradient(135deg, var(--teal), var(--purple));
  color: white;
  border: none;
  padding: 12px 24px;
  border-radius: 10px;
  cursor: pointer;
  font-weight: 600;
  width: 100%;
  font-size: 16px;
  transition: all 0.2s ease;
}

.scraper-button:hover{
  transform: scale(1.02);
  box-shadow: 0 8px 20px rgba(71, 200, 216, 0.3);
}

.stats{
  display: flex;
  gap: 15px;
  margin-top: 20px;
  text-align: center;
}

.stat{
  flex: 1;
  padding: 12px;
  background: rgba(255,255,255,0.03);
  border-radius: 8px;
}

.stat-number{
  font-size: 20px;
  font-weight: 700;
  color: var(--teal);
}

.stat-label{
  font-size: 12px;
  color: var(--muted);
  margin-top: 4px;
}

.icon{
  width: 24px;
  height: 24px;
  display: inline-block;
}

@media (max-width: 768px) {
  .scrapers-grid {
    grid-template-columns: 1fr;
  }
  h1 { font-size: 32px; }
  .top-nav { flex-direction: column; gap: 10px; }
}
</style>
</head>
<body>
<div class="container">
  <div class="top-nav">
    <div class="user-info">
      <span>Welcome, <strong>{{ user.username }}</strong>!</span>
    </div>
    <a href="{{ url_for('logout') }}" class="logout-btn">Logout</a>
  </div>

  <header>
    <h1>🌍 Terra Scrap</h1>
    <div class="subtitle">Multi-Website Scraping Platform</div>
    <div class="description">
      Select a website scraper to extract job listings, contact information, and more. 
      Each scraper is optimized for its specific target website with intelligent data extraction.
    </div>
  </header>

  <div class="scrapers-grid">
    {% for scraper_id, scraper in scrapers.items() %}
    <div class="scraper-card" onclick="window.location.href='/scraper/{{ scraper_id }}'">
      <div class="scraper-title">
        <span class="icon">🔍</span>
        {{ scraper.get_name() }}
      </div>
      <div class="scraper-description">
        {{ scraper.get_description() }}
      </div>
      <div class="scraper-url">
        {{ scraper.get_base_url() }}
      </div>
      <button class="scraper-button" onclick="event.stopPropagation(); window.location.href='/scraper/{{ scraper_id }}'">
        Launch Scraper
      </button>
      <div class="stats">
        <div class="stat">
          <div class="stat-number">∞</div>
          <div class="stat-label">Jobs Available</div>
        </div>
        <div class="stat">
          <div class="stat-number">✨</div>
          <div class="stat-label">Smart Extraction</div>
        </div>
        <div class="stat">
          <div class="stat-number">📊</div>
          <div class="stat-label">CSV Export</div>
        </div>
      </div>
    </div>
    {% endfor %}
  </div>
  
  <div style="text-align: center; margin-top: 50px; color: var(--muted); font-size: 14px;">
    <p>🚀 More scrapers coming soon! Add your favorite job sites and expand your reach.</p>
  </div>
</div>
</body>
</html>
"""

SCRAPER_HTML = """
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>{{ scraper.get_name() }} - Terra Scrap</title>
<style>
:root{
  --bg:#0a0e1a;
  --card:#0f1a2b;
  --muted:#a8cbd6;
  --accent:#f2d100;
  --accent2:#dd1818;
  --teal:#47c8d8;
  --purple:#8b5cf6;
}
body{
  font-family:Inter, system-ui, -apple-system, "Segoe UI", Roboto, Arial; 
  background:linear-gradient(180deg,var(--bg),#0e1726); 
  color:#e8f7f8; 
  margin:0;
  padding:28px;
}
.container{max-width:1200px;margin:0 auto}
.top-nav{
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  padding: 15px 20px;
  background: linear-gradient(180deg,var(--card),#0a1420);
  border-radius: 12px;
  border: 1px solid rgba(255,255,255,0.05);
}
.user-info{
  display: flex;
  align-items: center;
  gap: 15px;
  color: var(--muted);
}
.logout-btn{
  background: var(--accent2);
  color: white;
  border: none;
  padding: 8px 16px;
  border-radius: 6px;
  cursor: pointer;
  text-decoration: none;
  font-size: 14px;
}
header{display:flex;justify-content:space-between;align-items:center;gap:10px;margin-bottom:18px}
h1{margin:0;color:var(--teal);font-size:34px}
.back-btn{
  background: linear-gradient(135deg, var(--purple), var(--teal));
  color: white;
  border: none;
  padding: 10px 16px;
  border-radius: 8px;
  cursor: pointer;
  text-decoration: none;
  font-weight: 600;
}
.card{background:linear-gradient(180deg,var(--card),#052028); padding:20px;border-radius:12px;box-shadow:0 8px 30px rgba(0,0,0,0.5); margin-bottom:14px}
.controls{display:flex;gap:10px;align-items:center;flex-wrap:wrap}
input[type=number], input[type=text], select{background:#05282f;border:1px solid rgba(255,255,255,0.03);padding:8px;border-radius:8px;color:#dff7f9}
button{background:var(--teal);color:#022b2b;border:none;padding:10px 14px;border-radius:10px;cursor:pointer}
button.ghost{background:transparent;border:1px solid rgba(255,255,255,0.04);color:var(--teal)}
.summary{display:flex;gap:12px;align-items:center}
.stat{padding:10px 14px;border-radius:8px;background:rgba(255,255,255,0.03);min-width:140px;text-align:center}
table{width:100%;border-collapse:collapse;margin-top:10px;font-size:14px}
th,td{padding:12px;border-bottom:1px solid rgba(255,255,255,0.03);text-align:left}
th{font-weight:600;color:var(--muted);font-size:13px}
#logs{max-height:220px;overflow:auto;padding:8px;background:rgba(0,0,0,0.06);border-radius:8px;color:#bfeaf0;font-size:13px}
.top-controls{display:flex;gap:12px;align-items:center}
@media (max-width:900px){
  .controls{flex-direction:column;align-items:flex-start}
  header{flex-direction:column;align-items:flex-start;gap:8px}
  .top-nav { flex-direction: column; gap: 10px; }
}
a.link{color:var(--teal)}
</style>
</head>
<body>
<div class="container">
  <div class="top-nav">
    <div class="user-info">
      <span>Welcome, <strong>{{ user.username }}</strong>!</span>
    </div>
    <a href="{{ url_for('logout') }}" class="logout-btn">Logout</a>
  </div>

  <header>
    <div>
      <div style="display: flex; align-items: center; gap: 15px; margin-bottom: 8px;">
        <a href="/" class="back-btn">← Home</a>
        <h1>{{ scraper.get_name() }}</h1>
      </div>
      <div style="color:var(--muted)">{{ scraper.get_description() }}</div>
    </div>
    <div class="summary card" style="padding:12px 18px;">
      <div class="stat">Total rows:<div id="total" style="font-weight:700;font-size:18px;margin-top:6px">0</div></div>
      <div class="stat">Unique emails:<div id="unique" style="font-weight:700;font-size:18px;margin-top:6px">0</div></div>
      <div class="stat">Duplicate emails:<div id="duplicate" style="font-weight:700;font-size:18px;margin-top:6px">0</div></div>
    </div>
  </header>

  <div class="card">
    <div class="controls">
      <label>Start page <input id="start" type="number" value="1" style="width:100px"></label>
      <label>End page <input id="end" type="number" value="2" style="width:100px"></label>
      <button id="run">Run Scraper</button>
      <button id="stop" class="ghost">Stop</button>
      <button id="download">Download CSV</button>
      <button id="download_unique" class="ghost">Download Unique</button>
      <button id="download_dup" class="ghost">Download Duplicates</button>
      <div style="margin-left:auto"><input id="search" type="text" placeholder="Search company/title/email" style="width:320px"></div>
    </div>
    <div style="margin-top:10px;color:var(--muted);font-size:13px">Rows stream live as they are scraped. Use search to filter table.</div>
  </div>

  <div class="card">
    <h3>Live Job Table</h3>
    <table id="tbl">
      <thead><tr><th>#</th><th>Company</th><th>Job Title</th><th>Contact</th><th>Email</th><th>Website</th></tr></thead>
      <tbody></tbody>
    </table>
  </div>

  <div class="card">
    <h3>Logs</h3>
    <div id="logs"></div>
  </div>
</div>

<script>
const scraperId = '{{ scraper_id }}';
let evtSource = null;
let total = 0;
const tbody = document.querySelector('#tbl tbody');

function startEvents(){
  if(evtSource) evtSource.close();
  evtSource = new EventSource('/events/' + scraperId);
  evtSource.onmessage = (e) => {
    const obj = JSON.parse(e.data);
    if(obj.type === 'reset'){
      clearTableAndCounters();
    } else if(obj.type === 'row'){
      addRow(obj.row);
    } else if(obj.type === 'log'){
      addLog(obj.msg);
    } else if(obj.type === 'summary'){
      document.getElementById('total').textContent = obj.total;
      document.getElementById('unique').textContent = obj.unique;
      document.getElementById('duplicate').textContent = obj.duplicate;
    } else if(obj.type === 'done'){
      addLog('Scrape finished — total rows: ' + obj.total);
      if(evtSource){ evtSource.close(); evtSource = null; }
    }
  };
  evtSource.onerror = (err) => { addLog('EventSource error'); }
}

function clearTableAndCounters(){
  while(tbody.firstChild) tbody.removeChild(tbody.firstChild);
  document.getElementById('total').textContent = '0';
  document.getElementById('unique').textContent = '0';
  document.getElementById('duplicate').textContent = '0';
  total = 0;
  addLog('UI reset for new run');
}

function addRow(row){
  total += 1;
  const tr = document.createElement('tr');
  tr.innerHTML = `<td>${total}</td><td>${escapeHtml(row[1])}</td><td>${escapeHtml(row[0])}</td><td>${escapeHtml(row[2])}</td><td><a class="link" href="mailto:${escapeHtml(row[3])}">${escapeHtml(row[3])}</a></td><td><a class="link" target="_blank" href="${escapeHtml(row[10])}">${escapeHtml(row[10])}</a></td>`;
  tbody.prepend(tr);
  applyFilter();
}

function addLog(msg){
  const d = document.getElementById('logs');
  const el = document.createElement('div');
  el.textContent = new Date().toLocaleTimeString() + ' — ' + msg;
  d.prepend(el);
}

document.getElementById('run').onclick = async () => {
  const start = parseInt(document.getElementById('start').value || '1',10);
  const end = parseInt(document.getElementById('end').value || '2',10);
  if(evtSource) evtSource.close();
  startEvents();
  const res = await fetch('/start_scrape/' + scraperId, {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({start:start,end:end})});
  if(res.ok){ addLog('Scraper started.') } else { addLog('Failed to start scraper.') }
};

document.getElementById('stop').onclick = async () => {
  await fetch('/stop_scrape/' + scraperId,{method:'POST'});
  addLog('Stop requested.');
};

document.getElementById('download').onclick = () => { window.location = '/download/' + scraperId; };
document.getElementById('download_unique').onclick = () => { window.location = '/download_unique/' + scraperId; };
document.getElementById('download_dup').onclick = () => { window.location = '/download_duplicates/' + scraperId; };

document.getElementById('search').addEventListener('input', applyFilter);
function applyFilter(){
  const q = document.getElementById('search').value.trim().toLowerCase();
  if(!q){ for(const r of tbody.rows) r.style.display = ''; return; }
  for(const r of tbody.rows){
    const text = r.textContent.toLowerCase();
    r.style.display = text.includes(q) ? '' : 'none';
  }
}

function escapeHtml(s){ if(!s) return ''; return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }
</script>
</body>
</html>
"""

if __name__ == "__main__":
    import os
    
    # Production environment variables
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'terra-scrap-secret-key-change-in-production')
    app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME', 'rgsiddhu5252@gmail.com')
    app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD', 'miblzeeoegkhtnbq')
    
    # Database configuration
    database_url = os.environ.get('DATABASE_URL', 'sqlite:///terra_scrap.db')
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    
    # Initialize database
    with app.app_context():
        db.create_all()
        
        # Auto-create test user in production if it doesn't exist
        existing_user = User.query.filter_by(email='mprasanth18@gmail.com').first()
        if not existing_user:
            test_user = User(
                username='mprasanth18',
                email='mprasanth18@gmail.com'
            )
            test_user.set_password('IAmTheBest@1')
            test_user.is_approved = True
            test_user.is_active = True
            db.session.add(test_user)
            db.session.commit()
            print("✅ Test user created for production")
    
    # Run the application
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get('FLASK_ENV') == 'development'
    app.run(host="0.0.0.0", port=port, debug=debug, threaded=True)