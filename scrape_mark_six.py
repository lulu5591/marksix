import os
import re
import sqlite3
import time
from html import unescape
from urllib.parse import urljoin
from urllib.request import Request, urlopen

BASE_URL = "https://lottery.hk/en/mark-six/results/"
DB_PATH = os.path.join("data", "mark_six.sqlite")

def fetch(url):
    req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    for _ in range(3):
        with urlopen(req, timeout=30) as r:
            b = r.read()
            if b:
                return b.decode("utf-8", errors="ignore")
        time.sleep(1)
    return ""

def to_text(html):
    t = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.I)
    t = re.sub(r"<style[\s\S]*?</style>", " ", t, flags=re.I)
    t = re.sub(r"<[^>]+>", " ", t)
    t = unescape(t)
    t = re.sub(r"\s+", " ", t).strip()
    return t

def extract_links(html, base):
    hrefs = set()
    for m in re.finditer(r"href=\"([^\"]+)\"", html, flags=re.I):
        h = m.group(1)
        if "/mark-six/results" in h:
            hrefs.add(urljoin(base, h))
    return sorted(hrefs)

def parse_date(d):
    m = re.match(r"(\d{2})/(\d{2})/(\d{4})", d)
    if not m:
        return None
    dd, mm, yyyy = m.groups()
    return f"{yyyy}-{mm}-{dd}"

def extract_draws(text):
    draws = []
    it = list(re.finditer(r"(\d{2}/\d{3})\s+(\d{2}/\d{2}/\d{4})", text))
    for m in it:
        dn = m.group(1)
        dd = parse_date(m.group(2))
        start = m.end()
        window = text[start:start+1000]
        nums = [int(x) for x in re.findall(r"\b([1-9]|[1-4]\d)\b", window)]
        if len(nums) >= 7:
            n = nums[:7]
            draws.append({
                "draw_number_text": dn,
                "draw_date": dd,
                "numbers": n[:6],
                "extra": n[6]
            })
    return draws

def init_db(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS mark_six_draws (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            draw_number_text TEXT UNIQUE,
            draw_year INTEGER,
            draw_date TEXT,
            n1 INTEGER,
            n2 INTEGER,
            n3 INTEGER,
            n4 INTEGER,
            n5 INTEGER,
            n6 INTEGER,
            extra INTEGER,
            source_url TEXT
        )
        """
    )
    conn.commit()
    return conn

def save_draws(conn, source_url, items):
    cur = conn.cursor()
    for d in items:
        y = int(d["draw_date"].split("-")[0]) if d["draw_date"] else None
        n = d["numbers"]
        cur.execute(
            """
            INSERT OR IGNORE INTO mark_six_draws (
                draw_number_text, draw_year, draw_date,
                n1, n2, n3, n4, n5, n6, extra, source_url
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                d["draw_number_text"], y, d["draw_date"],
                n[0], n[1], n[2], n[3], n[4], n[5], d["extra"], source_url
            )
        )
    conn.commit()

def main():
    conn = init_db(DB_PATH)
    html = fetch(BASE_URL)
    if not html:
        return
    links = extract_links(html, BASE_URL)
    seen = set()
    for u in [BASE_URL] + links:
        if u in seen:
            continue
        seen.add(u)
        h = fetch(u)
        if not h:
            continue
        t = to_text(h)
        items = extract_draws(t)
        if items:
            save_draws(conn, u, items)
        time.sleep(0.5)
    conn.close()

if __name__ == "__main__":
    main()

