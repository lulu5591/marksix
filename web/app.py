import os
import random
import sqlite3
import time
import runpy
from flask import Flask, render_template, request, redirect, url_for, jsonify

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "mark_six.sqlite")

app = Flask(__name__)

def get_conn():
    return sqlite3.connect(DB_PATH)

def row_to_combo(row):
    nums = sorted([row[0], row[1], row[2], row[3], row[4], row[5]])
    return "-".join(str(x) for x in nums)

def load_existing_combos():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("select n1,n2,n3,n4,n5,n6 from mark_six_draws")
    s = set()
    for r in cur.fetchall():
        s.add(row_to_combo(r))
    conn.close()
    return s

EXISTING = load_existing_combos()

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/history")
def history():
    page = int(request.args.get("page", 1))
    size = 50
    q = request.args.get("q", "").strip()
    conn = get_conn()
    cur = conn.cursor()
    base = "select draw_number_text, draw_date, n1,n2,n3,n4,n5,n6, extra from mark_six_draws"
    where = []
    params = []
    if q:
        where.append("(draw_number_text like ? or draw_date like ?)" )
        params.extend([f"%{q}%", f"%{q}%"]) 
    sql_count = f"select count(*) from mark_six_draws {'where ' + ' and '.join(where) if where else ''}"
    cur.execute(sql_count, params)
    total = cur.fetchone()[0]
    total_pages = (total + size - 1) // size if total > 0 else 1
    if page < 1:
        page = 1
    if page > total_pages:
        page = total_pages
    offset = (page - 1) * size
    sql = f"{base} {'where ' + ' and '.join(where) if where else ''} order by draw_date desc limit ? offset ?"
    cur.execute(sql, params + [size, offset])
    rows = cur.fetchall()
    conn.close()
    msg = request.args.get("msg")
    return render_template("history.html", rows=rows, page=page, total_pages=total_pages, q=q, msg=msg)

def parse_nums(s):
    parts = [p for p in s.replace(",", " ").split() if p]
    nums = []
    for p in parts:
        try:
            v = int(p)
        except ValueError:
            continue
        if 1 <= v <= 49:
            nums.append(v)
    nums = sorted(nums)[:6]
    return nums

@app.route("/predict", methods=["GET", "POST"])
def predict():
    exists = None
    candidate = None
    suggestion = None
    smart = None
    message = None
    trend = compute_trends(200)
    if request.method == "POST":
        action = request.form.get("action")
        if action == "check":
            nums = parse_nums(request.form.get("numbers", ""))
            if len(nums) != 6:
                message = "Enter six numbers between 1 and 49"
            else:
                combo = "-".join(str(x) for x in nums)
                exists = combo in EXISTING
                candidate = nums
        elif action == "suggest":
            tries = 0
            while tries < 5000:
                pick = sorted(random.sample(range(1, 50), 6))
                combo = "-".join(str(x) for x in pick)
                if combo not in EXISTING:
                    suggestion = pick
                    break
                tries += 1
            if suggestion is None:
                message = "No new combination found in attempts; try again"
        elif action == "smart":
            window = request.form.get("window")
            try:
                w = int(window) if window else 200
            except ValueError:
                w = 200
            smart = smart_suggest(w)
            if smart is None:
                message = "No smart suggestion found; try increasing window or retry"
    return render_template("predict.html", exists=exists, candidate=candidate, suggestion=suggestion, smart=smart, message=message, trend=trend)

def fetch_all_numbers():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("select n1,n2,n3,n4,n5,n6 from mark_six_draws")
    rows = cur.fetchall()
    conn.close()
    return rows

def longest_consecutive_run(nums):
    s = sorted(nums)
    best = 1
    cur = 1
    for i in range(1, len(s)):
        if s[i] == s[i-1] + 1:
            cur += 1
            if cur > best:
                best = cur
        elif s[i] != s[i-1]:
            cur = 1
    return best

def decade(n):
    return (n - 1) // 10

@app.route("/insights")
def insights():
    rows = fetch_all_numbers()
    total = len(rows)
    distinct = len(EXISTING)
    parity_counts = {k: 0 for k in range(7)}
    run_counts = {k: 0 for k in range(1, 7)}
    same_decade_all = 0
    last_digit_all = 0
    for r in rows:
        nums = list(r)
        evens = sum(1 for x in nums if x % 2 == 0)
        parity_counts[evens] += 1
        run = longest_consecutive_run(nums)
        run_counts[run] += 1
        decs = {decade(x) for x in nums}
        if len(decs) == 1:
            same_decade_all += 1
        last_digits = {x % 10 for x in nums}
        if len(last_digits) == 1:
            last_digit_all += 1
    never_patterns = []
    rare_patterns = []
    if distinct == total:
        never_patterns.append("Exact six-number combination never repeats")
    if run_counts.get(6, 0) == 0:
        never_patterns.append("Run of 6 consecutive numbers never occurs")
    if run_counts.get(5, 0) > 0:
        rare_patterns.append(f"Run of 5 consecutive numbers occurs {run_counts.get(5,0)} time(s)")
    if parity_counts.get(6, 0) == 0:
        rare_patterns.append("All-even combinations are rare")
    if parity_counts.get(0, 0) == 0:
        rare_patterns.append("All-odd combinations are rare")
    if same_decade_all == 0:
        never_patterns.append("All six numbers from the same decade (e.g., 10–19) never occur")
    if last_digit_all == 0:
        never_patterns.append("All six sharing the same last digit is mathematically impossible in 1–49")
    return render_template(
        "insights.html",
        total=total,
        distinct=distinct,
        parity_counts=parity_counts,
        run_counts=run_counts,
        same_decade_all=same_decade_all,
        last_digit_all=last_digit_all,
        never_patterns=never_patterns,
        rare_patterns=rare_patterns,
    )

@app.route("/api/exists")
def api_exists():
    s = request.args.get("nums", "")
    nums = parse_nums(s)
    if len(nums) != 6:
        return jsonify({"ok": False, "error": "need six numbers 1-49"}), 400
    combo = "-".join(str(x) for x in nums)
    return jsonify({"ok": True, "exists": combo in EXISTING, "combo": combo})

def create_app():
    return app

def fetch_recent_rows(limit):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("select draw_date, n1,n2,n3,n4,n5,n6 from mark_six_draws order by draw_date desc limit ?", (limit,))
    rows = cur.fetchall()
    conn.close()
    return rows

def compute_trends(limit):
    rows = fetch_recent_rows(limit)
    counts = {i: 0 for i in range(1, 50)}
    last_seen = {i: None for i in range(1, 50)}
    for r in rows:
        d = r[0]
        for x in r[1:]:
            counts[x] += 1
            if last_seen[x] is None:
                last_seen[x] = d
    ranked = sorted([(n, counts[n], last_seen[n]) for n in range(1, 50)], key=lambda t: t[1], reverse=True)
    return ranked[:15]

def valid_smart(nums):
    if len(nums) != 6:
        return False
    if sum(1 for x in nums if x % 2 == 0) != 3:
        return False
    if longest_consecutive_run(nums) > 2:
        return False
    return True

def smart_suggest(limit):
    ranked = compute_trends(limit)
    order = [n for n, c, ld in ranked]
    evens = [n for n in order if n % 2 == 0]
    odds = [n for n in order if n % 2 == 1]
    pool_even = evens + [n for n in range(1, 50) if n % 2 == 0 and n not in evens]
    pool_odd = odds + [n for n in range(1, 50) if n % 2 == 1 and n not in odds]
    tries = 0
    while tries < 5000:
        pick_e = []
        pick_o = []
        pe = pool_even[:15] if len(pool_even) >= 15 else pool_even
        po = pool_odd[:15] if len(pool_odd) >= 15 else pool_odd
        while len(pick_e) < 3 and pe:
            x = random.choice(pe)
            pe.remove(x)
            pick_e.append(x)
        while len(pick_o) < 3 and po:
            x = random.choice(po)
            po.remove(x)
            pick_o.append(x)
        cand = sorted(pick_e + pick_o)
        if not valid_smart(cand):
            tries += 1
            continue
        combo = "-".join(str(x) for x in cand)
        if combo in EXISTING:
            tries += 1
            continue
        return cand
    return None

@app.route("/update", methods=["POST"])
def update():
    before = 0
    after = 0
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("select count(*) from mark_six_draws")
        before = cur.fetchone()[0]
        conn.close()
    except Exception:
        before = 0
    try:
        added = incremental_update()
    except Exception as e:
        return redirect(url_for("history", msg=f"Update failed: {e}"))
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("select count(*) from mark_six_draws")
        after = cur.fetchone()[0]
        conn.close()
    except Exception:
        after = before
    delta = added if added is not None else (after - before)
    return redirect(url_for("history", msg=f"Updated: +{delta} new draws (total {after})"))

def existing_draw_numbers():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("select draw_number_text from mark_six_draws")
    s = {r[0] for r in cur.fetchall()}
    conn.close()
    return s

def fetch_html(url):
    import urllib.request
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        b = r.read()
        return b.decode("utf-8", errors="ignore")

def to_text(html):
    import re
    from html import unescape
    t = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.I)
    t = re.sub(r"<style[\s\S]*?</style>", " ", t, flags=re.I)
    t = re.sub(r"<[^>]+>", " ", t)
    t = unescape(t)
    t = re.sub(r"\s+", " ", t).strip()
    return t

def parse_incremental_draws(text):
    import re
    def parse_date(d):
        m = re.match(r"(\d{2})/(\d{2})/(\d{4})", d)
        if not m:
            return None
        dd, mm, yyyy = m.groups()
        return f"{yyyy}-{mm}-{dd}"
    items = []
    it = list(re.finditer(r"(\d{2}/\d{3})\s+(\d{2}/\d{2}/\d{4})", text))
    for m in it:
        dn = m.group(1)
        dd = parse_date(m.group(2))
        start = m.end()
        window = text[start:start+1000]
        nums = [int(x) for x in re.findall(r"\b([1-9]|[1-4]\d)\b", window)]
        if len(nums) >= 7:
            n = nums[:7]
            items.append({
                "draw_number_text": dn,
                "draw_date": dd,
                "numbers": n[:6],
                "extra": n[6]
            })
    return items

def incremental_update():
    base = "https://lottery.hk/en/mark-six/results/"
    html = fetch_html(base)
    text = to_text(html)
    items = parse_incremental_draws(text)
    existing = existing_draw_numbers()
    conn = get_conn()
    cur = conn.cursor()
    added = 0
    for d in items:
        if d["draw_number_text"] in existing:
            continue
        n = d["numbers"]
        cur.execute(
            """
            INSERT OR IGNORE INTO mark_six_draws (
                draw_number_text, draw_year, draw_date,
                n1, n2, n3, n4, n5, n6, extra, source_url
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                d["draw_number_text"], int(d["draw_date"].split("-")[0]) if d["draw_date"] else None, d["draw_date"],
                n[0], n[1], n[2], n[3], n[4], n[5], d["extra"], base
            )
        )
        added += 1
    conn.commit()
    conn.close()
    return added

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8000, debug=True)
