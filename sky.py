#!/usr/bin/env python3
"""
Nebula · MakeIt Scraper (final single-file app)
- run-local counters & reset so each run shows only the current run's rows
- strong DOM-aware contact extraction
- live SSE streaming to browser
- download CSV / unique / duplicate CSVs
- Germany-themed colorful UI
"""

from flask import Flask, render_template_string, request, Response, send_file, jsonify
import threading, queue, time, random, os, csv, re, io
import requests
from bs4 import BeautifulSoup, NavigableString, Tag
from urllib.parse import urljoin

# ---------------- CONFIG ----------------
BASE_LISTING = "https://www.make-it-in-germany.com/en/working-in-germany/job-listings?page="
OUTPUT_CSV = "job_contacts_live.csv"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                         "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"}
DELAY_MIN = 0.4
DELAY_MAX = 1.0
REQUEST_TIMEOUT = 18
# ----------------------------------------

email_re = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}", re.I)
honorific_re = re.compile(r"\b(Dr|Dr\.|Mr|Mrs|Ms|Miss|Mister|Herr|Frau|Professor|Prof\.?)\b", re.I)
titlecase_name_re = re.compile(r"^[A-ZÄÖÜ][a-zäöüß]+(?:[ \-][A-ZÄÖÜ][a-zäöüß]+)+$")

app = Flask(__name__)
event_queue = queue.Queue()
scraper_thread = None
scraper_stop_flag = threading.Event()

# cumulative state (persisted in CSV) - used only for cumulative bookkeeping if needed
seen_emails_freq = {}         # email -> cumulative count
total_rows_cumulative = 0

# run-local state (cleared at start of each run) - used for live UI counters
run_total_rows = 0
run_seen_emails = {}         # email -> count for current run

# ---------------- helpers ----------------
def clean_text(s):
    if not s:
        return "N/A"
    s = s.replace("\xa0", " ")
    s = re.sub(r"\s+", " ", s).strip()
    return s if s else "N/A"

def request_get(url, retries=3):
    for attempt in range(retries):
        try:
            r = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
            r.raise_for_status()
            if not r.encoding:
                r.encoding = "utf-8"
            return r.text
        except Exception as e:
            event_queue.put({"type":"log","msg":f"Request error for {url}: {e} — retry {attempt+1}/{retries}"})
            time.sleep(1 + attempt)
    # final try (raise if fails)
    r = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
    r.raise_for_status()
    return r.text

def parse_listing_page(html, base_url):
    soup = BeautifulSoup(html, "lxml")
    jobs = []
    for art in soup.select("li.list__item article"):
        h3 = art.select_one("h3")
        p = art.select_one("p")
        a = art.select_one("a.btn")
        title = clean_text(h3.get_text()) if h3 else "N/A"
        company = clean_text(p.get_text()) if p else "N/A"
        url = urljoin(base_url, a["href"]) if a and a.has_attr("href") else "N/A"
        jobs.append({"title": title, "company": company, "job_url": url})
    return jobs

# DOM helpers for robust extraction
def find_value_after_label(node, max_steps=20):
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

def find_label_value_html(soup, label_patterns, company_hint=None):
    for patt in label_patterns:
        for node in soup.find_all(string=re.compile(patt, re.I)):
            val = find_value_after_label(node)
            if val:
                val = val.strip()
                if val and "http" not in val.lower():
                    return clean_text(val)
    for patt in label_patterns:
        for tag in soup.find_all(['strong','b','label','h3','h4','p','div','li'], string=re.compile(patt, re.I)):
            val = find_value_after_label(tag)
            if val:
                val = val.strip()
                if val and "http" not in val.lower():
                    return clean_text(val)
    for patt in label_patterns:
        for tag in soup.find_all(['p','div','li','span','td'], string=re.compile(patt + r".*", re.I)):
            text = tag.get_text(" ", strip=True)
            if ":" in text:
                parts = text.split(":",1)
                if len(parts) > 1:
                    return clean_text(parts[1])
    return None

def extract_contact_dom(soup):
    aside = soup.find("aside")
    search_labels = [r"Contact person", r"Contact person:", r"Contact:", r"Kontakt", r"Kontaktperson", r"Questions and applications to", r"Questions and applications"]
    if aside:
        val = find_label_value_html(aside, search_labels)
        if val and val.strip():
            return val
    val = find_label_value_html(soup, search_labels)
    if val and val.strip():
        return val
    best = (0, "")
    for t in soup.find_all(string=True):
        txt = t.strip()
        if not txt or len(txt) < 2: continue
        if re.search(r"@|http|www\.|\+?\d{2,}", txt): continue
        score = 0
        if honorific_re.search(txt): score = 3
        elif titlecase_name_re.match(txt): score = 2
        elif re.match(r"^[A-ZÄÖÜ][a-zäöüß]+ [A-ZÄÖÜ][a-zäöüß]+$", txt): score = 1
        if score > best[0]:
            best = (score, txt)
    if best[0] > 0:
        return clean_text(best[1])
    return "N/A"

def extract_detail_fields(html):
    soup = BeautifulSoup(html, "lxml")
    email = "N/A"
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if href.lower().startswith("mailto:"):
            cand = href.split("mailto:")[-1].split("?")[0].strip()
            if email_re.match(cand):
                email = cand
                break
    if email == "N/A":
        m = email_re.search(soup.get_text(" ", strip=True))
        if m:
            email = m.group(0)
    contact = extract_contact_dom(soup)
    refnum = find_label_value_html(soup, [r"Reference number", r"Reference no", r"Reference"]) or "N/A"
    workplace = find_label_value_html(soup, [r"Workplace"]) or "N/A"
    job_offer_type = find_label_value_html(soup, [r"Type of job offer", r"Type of job"]) or "N/A"
    employment_contract = find_label_value_html(soup, [r"Type of employment contract", r"Type of employment"]) or "N/A"
    online_since = find_label_value_html(soup, [r"Online since"]) or "N/A"
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

# ---------------- CSV helpers ----------------
def ensure_csv_header(path):
    if not os.path.exists(path):
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["Job Title","Company","Contact Name","Email","Job URL","Reference Number","Workplace","Type of job offer","Type of employment contract","Online since","Website","Source Page","Index"])
            f.flush()

def append_row_and_sync(path, row):
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(row)
        f.flush()
        try:
            os.fsync(f.fileno())
        except Exception:
            pass

def generate_unique_csv():
    if not os.path.exists(OUTPUT_CSV):
        return None
    seen = set()
    out = io.StringIO()
    w = csv.writer(out)
    with open(OUTPUT_CSV, newline='', encoding='utf-8') as f:
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

def generate_duplicates_csv():
    if not os.path.exists(OUTPUT_CSV):
        return None
    freq = {}
    rows_by_email = {}
    with open(OUTPUT_CSV, newline='', encoding='utf-8') as f:
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

# ---------------- helper to load cumulative CSV state (optional)
def load_existing_csv_state():
    global seen_emails_freq, total_rows_cumulative
    seen_emails_freq.clear()
    total_rows_cumulative = 0
    if not os.path.exists(OUTPUT_CSV):
        return
    with open(OUTPUT_CSV, newline='', encoding='utf-8') as f:
        r = csv.reader(f)
        header = next(r, None)
        for row in r:
            total_rows_cumulative += 1
            if len(row) > 3:
                email = row[3].strip()
                if email and email.upper() != "N/A" and email_re.match(email):
                    seen_emails_freq[email] = seen_emails_freq.get(email, 0) + 1
    # send a summary so UI may display cumulative if desired
    event_queue.put({"type":"log","msg":f"Loaded existing CSV: {total_rows_cumulative} rows, {len(seen_emails_freq)} unique emails (cumulative)."})

# ---------------- scraper worker (uses run-local counters) ----------------
def scraper_worker(start_page, end_page):
    global run_total_rows, run_seen_emails, total_rows_cumulative, seen_emails_freq
    ensure_csv_header(OUTPUT_CSV)
    for page in range(start_page, end_page+1):
        if scraper_stop_flag.is_set():
            event_queue.put({"type":"log","msg":"Scraper stopped by user."})
            break
        listing_url = BASE_LISTING + str(page)
        event_queue.put({"type":"log","msg":f"Loading listing page {page}..."})
        try:
            listing_html = request_get(listing_url)
        except Exception as e:
            event_queue.put({"type":"log","msg":f"Failed to load listing page {page}: {e}"})
            continue

        jobs = parse_listing_page(listing_html, listing_url)
        event_queue.put({"type":"log","msg":f"Found {len(jobs)} jobs on page {page}"})
        for idx, job in enumerate(jobs, start=1):
            if scraper_stop_flag.is_set():
                break
            title = job.get("title","N/A")
            company = job.get("company","N/A")
            job_url = job.get("job_url","N/A")
            contact = "N/A"; email = "N/A"
            refnum = workplace = job_offer_type = employment_contract = online_since = website = "N/A"
            if job_url != "N/A":
                try:
                    detail_html = request_get(job_url)
                    contact, email, refnum, workplace, job_offer_type, employment_contract, online_since, website = extract_detail_fields(detail_html)
                except Exception as e:
                    event_queue.put({"type":"log","msg":f"Detail fetch failed for {job_url}: {e}"})
            # update run-local counters
            run_total_rows += 1
            # update cumulative counters too (we keep CSV cumulative)
            total_rows_cumulative += 1

            email_norm = (email or "").strip()
            if email_norm and email_norm.upper() != "N/A" and email_re.match(email_norm):
                run_seen_emails[email_norm] = run_seen_emails.get(email_norm, 0) + 1
                seen_emails_freq[email_norm] = seen_emails_freq.get(email_norm, 0) + 1

            # append cumulative CSV
            row = [title, company, contact, email, job_url, refnum, workplace, job_offer_type, employment_contract, online_since, website, page, idx]
            append_row_and_sync(OUTPUT_CSV, row)

            # emit row and run-level summary
            event_queue.put({"type":"row","row":row})
            unique_count_run = len(run_seen_emails)
            total_emails_run = sum(run_seen_emails.values())
            duplicate_count_run = max(0, total_emails_run - unique_count_run)
            event_queue.put({"type":"summary","total": run_total_rows, "unique": unique_count_run, "duplicate": duplicate_count_run})

            time.sleep(DELAY_MIN + random.random() * (DELAY_MAX - DELAY_MIN))
    event_queue.put({"type":"done","total": run_total_rows})
    return

# ---------------- Flask routes & UI ----------------
INDEX_HTML = """
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>Nebula · MakeIt Scraper</title>
<style>
:root{
  --bg:#071021;
  --card:#0b2230;
  --muted:#a8cbd6;
  --accent:#f2d100; /* german gold accent */
  --accent2:#dd1818; /* german red */
  --teal:#47c8d8;
}
body{font-family:Inter, system-ui, -apple-system, "Segoe UI", Roboto, Arial; background:linear-gradient(180deg,var(--bg),#071726); color:#e8f7f8; margin:0;padding:28px}
.container{max-width:1200px;margin:0 auto}
header{display:flex;justify-content:space-between;align-items:center;gap:10px;margin-bottom:18px}
h1{margin:0;color:var(--teal);font-size:34px}
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
      <h1>Nebula · MakeIt Scraper</h1>
      <div style="color:var(--muted)">Live scraping dashboard — Germany-theme & live counts</div>
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
let evtSource = null;
let total = 0;
const tbody = document.querySelector('#tbl tbody');

function startEvents(){
  if(evtSource) evtSource.close();
  evtSource = new EventSource('/events');
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
  // clear table
  while(tbody.firstChild) tbody.removeChild(tbody.firstChild);
  // reset counters
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
  const res = await fetch('/start_scrape', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({start:start,end:end})});
  if(res.ok){ addLog('Scraper started.') } else { addLog('Failed to start scraper.') }
};

document.getElementById('stop').onclick = async () => {
  await fetch('/stop_scrape',{method:'POST'});
  addLog('Stop requested.');
};

document.getElementById('download').onclick = () => { window.location = '/download'; };
document.getElementById('download_unique').onclick = () => { window.location = '/download_unique'; };
document.getElementById('download_dup').onclick = () => { window.location = '/download_duplicates'; };

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

@app.route('/')
def index():
    return render_template_string(INDEX_HTML)

@app.route('/start_scrape', methods=['POST'])
def start_scrape():
    global scraper_thread, run_total_rows, run_seen_emails
    data = request.get_json(force=True)
    start = int(data.get('start', 1))
    end = int(data.get('end', 1))
    if scraper_thread and scraper_thread.is_alive():
        return jsonify({"status":"already_running"}), 400

    # Reset run-local counters so UI shows only this run
    run_total_rows = 0
    run_seen_emails = {}

    # tell client(s) to reset UI
    event_queue.put({"type":"reset"})

    ensure_csv_header(OUTPUT_CSV)
    # optionally load cumulative CSV state (not used for run counts)
    load_existing_csv_state()

    scraper_stop_flag.clear()
    scraper_thread = threading.Thread(target=scraper_worker, args=(start,end), daemon=True)
    scraper_thread.start()
    return jsonify({"status":"started","start":start,"end":end})

@app.route('/stop_scrape', methods=['POST'])
def stop_scrape():
    scraper_stop_flag.set()
    return jsonify({"status":"stopping"})

@app.route('/events')
def sse_events():
    def gen():
        while True:
            try:
                item = event_queue.get(timeout=0.5)
            except queue.Empty:
                if not (scraper_thread and scraper_thread.is_alive()) and event_queue.empty():
                    break
                continue
            import json
            yield f"data: {json.dumps(item)}\n\n"
            if item.get("type") == "done":
                break
    return Response(gen(), mimetype='text/event-stream')

@app.route('/download')
def download():
    if not os.path.exists(OUTPUT_CSV):
        return "No CSV yet", 404
    return send_file(OUTPUT_CSV, as_attachment=True)

@app.route('/download_unique')
def download_unique():
    out = generate_unique_csv()
    if not out:
        return "No CSV yet", 404
    return Response(out.getvalue(), mimetype='text/csv', headers={"Content-disposition":"attachment; filename=unique_emails.csv"})

@app.route('/download_duplicates')
def download_duplicates():
    out = generate_duplicates_csv()
    if not out:
        return "No CSV yet", 404
    return Response(out.getvalue(), mimetype='text/csv', headers={"Content-disposition":"attachment; filename=duplicate_emails.csv"})

if __name__ == "__main__":
    ensure_csv_header(OUTPUT_CSV)
    load_existing_csv_state()
    app.run(debug=True, threaded=True)
    
from flask import Flask, render_template, request

