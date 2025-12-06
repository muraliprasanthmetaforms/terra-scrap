#!/usr/bin/env python3
"""
Terra Scrap - Multi-Website Scraping Platform
A Flask-based web scraping application that supports multiple websites
with a home page to select which website to scrape from.
"""

from flask import Flask, render_template_string, request, Response, send_file, jsonify, redirect, url_for
import threading, queue, time, random, os, csv, re, io
import requests
from bs4 import BeautifulSoup, NavigableString, Tag
from urllib.parse import urljoin
from abc import ABC, abstractmethod
from typing import Dict, List, Optional

app = Flask(__name__)

# Global state
event_queues = {}  # scraper_id -> queue
scraper_threads = {}  # scraper_id -> thread
scraper_stop_flags = {}  # scraper_id -> threading.Event

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

# Flask Routes
@app.route('/')
def home():
    """Home page showing list of available scrapers"""
    return render_template_string(HOME_HTML, scrapers=SCRAPERS)

@app.route('/scraper/<scraper_id>')
def scraper_page(scraper_id):
    """Individual scraper page"""
    scraper = get_scraper(scraper_id)
    if not scraper:
        return "Scraper not found", 404
    return render_template_string(SCRAPER_HTML, scraper=scraper, scraper_id=scraper_id)

@app.route('/start_scrape/<scraper_id>', methods=['POST'])
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
def stop_scrape(scraper_id):
    stop_flag = scraper_stop_flags.get(scraper_id)
    if stop_flag:
        stop_flag.set()
    return jsonify({"status":"stopping"})

@app.route('/events/<scraper_id>')
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
def download(scraper_id):
    scraper = get_scraper(scraper_id)
    if not scraper:
        return "Scraper not found", 404
    
    csv_path = scraper.get_csv_filename()
    if not os.path.exists(csv_path):
        return "No CSV yet", 404
    return send_file(csv_path, as_attachment=True)

@app.route('/download_unique/<scraper_id>')
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

# HTML Templates
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
  --accent:#f2d100; /* gold accent */
  --accent2:#dd1818; /* red */
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
}
</style>
</head>
<body>
<div class="container">
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
}
a.link{color:var(--teal)}
</style>
</head>
<body>
<div class="container">
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
    app.run(debug=True, threaded=True)