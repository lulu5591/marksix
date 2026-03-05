import os
import random
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, jsonify
import urllib.request
import re
from html import unescape
import socket, ssl, math

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "mark_six.sqlite")

app = Flask(__name__)

RED_NUMS = {1, 2, 7, 8, 12, 13, 18, 19, 23, 24, 29, 30, 34, 35, 40, 45, 46}
BLUE_NUMS = {3, 4, 9, 10, 14, 15, 20, 25, 26, 31, 36, 37, 41, 42, 47, 48}
GREEN_NUMS = {5, 6, 11, 16, 17, 21, 22, 27, 28, 32, 33, 38, 39, 43, 44, 49}

def ball_color(n: int) -> str:
    if n in RED_NUMS:
        return "red"
    if n in BLUE_NUMS:
        return "blue"
    if n in GREEN_NUMS:
        return "green"
    return "neutral"

app.jinja_env.globals.update(ball_color=ball_color)

def get_conn():
    return sqlite3.connect(DB_PATH)

def get_latest_and_total():
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("select max(draw_date), count(*) from mark_six_draws")
        latest, total = cur.fetchone()
        conn.close()
        return latest, total
    except Exception:
        return None, 0

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

def reload_existing():
    global EXISTING
    EXISTING = load_existing_combos()

@app.route("/")
def index():
    latest, total = get_latest_and_total()
    return render_template("index.html", latest=latest, total=total)

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
        where.append("(draw_number_text like ? or draw_date like ?)")
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
    latest, total_now = get_latest_and_total()
    return render_template("history.html", rows=rows, page=page, total_pages=total_pages, q=q, msg=msg, latest=latest, total_now=total_now)

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
    smart_label = None
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
        elif action == "smart_unified":
            preset = request.form.get("preset", "default")
            def read_int(name, default):
                try:
                    return int(request.form.get(name) or default)
                except ValueError:
                    return default
            w = read_int("window", 200)
            if preset == "default":
                smart = smart_suggest(w)
                smart_label = "Smart (default)"
            elif preset == "conservative":
                smart = smart_suggest_conservative(w)
                smart_label = "Smart (conservative)"
            elif preset == "exploratory":
                smart = smart_suggest_exploratory(w)
                smart_label = "Smart (exploratory)"
            else:
                even_count = read_int("even_count", 3)
                max_run = read_int("max_run", 2)
                top_k = read_int("top_k", 15)
                cooldown = read_int("cooldown", 0)
                weighted = True if request.form.get("weighted") == "on" else False
                smart = smart_suggest_custom(w, even_count, max_run, top_k, cooldown, weighted)
                smart_label = f"Custom (even={even_count}, run≤{max_run})"
            if smart is None:
                message = "No smart suggestion found; try relaxing constraints or changing window"
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
    return render_template("predict.html", exists=exists, candidate=candidate, suggestion=suggestion, smart=smart, smart_label=smart_label, message=message, trend=trend)

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
        if s[i] == s[i - 1] + 1:
            cur += 1
            if cur > best:
                best = cur
        elif s[i] != s[i - 1]:
            cur = 1
    return best

def decade(n):
    return (n - 1) // 10

@app.route("/insights")
def insights():
    rows = fetch_all_numbers()
    total = len(rows)
    distinct = len({row_to_combo(r) for r in rows})
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
    M = math.comb(49, 6)
    p_consec6 = 44 / M
    expected_consec6 = total * p_consec6
    p_all_even = math.comb(24, 6) / M
    p_all_odd = math.comb(25, 6) / M
    exp_all_even = total * p_all_even
    exp_all_odd = total * p_all_odd
    p_same_decade = (4 * math.comb(10, 6) + math.comb(9, 6)) / M
    exp_same_decade = total * p_same_decade
    expected_repeats = (total * (total - 1)) / (2 * M)
    observed_repeats = total - distinct
    math_impossible = ["All six sharing the same last digit (max per digit is 5 in 1–49)"]
    rarity_estimates = [
        {"pattern": "Six consecutive numbers", "observed": run_counts.get(6, 0), "expected": expected_consec6},
        {"pattern": "All-even", "observed": parity_counts.get(6, 0), "expected": exp_all_even},
        {"pattern": "All-odd", "observed": parity_counts.get(0, 0), "expected": exp_all_odd},
        {"pattern": "All six in same decade", "observed": same_decade_all, "expected": exp_same_decade},
        {"pattern": "Exact-combo repeats", "observed": observed_repeats, "expected": expected_repeats},
    ]
    return render_template(
        "insights.html",
        total=total,
        distinct=distinct,
        parity_counts=parity_counts,
        run_counts=run_counts,
        same_decade_all=same_decade_all,
        last_digit_all=last_digit_all,
        math_impossible=math_impossible,
        rarity_estimates=rarity_estimates,
    )

@app.route("/api/exists")
def api_exists():
    s = request.args.get("nums", "")
    nums = parse_nums(s)
    if len(nums) != 6:
        return jsonify({"ok": False, "error": "need six numbers 1-49"}), 400
    combo = "-".join(str(x) for x in nums)
    return jsonify({"ok": True, "exists": combo in EXISTING, "combo": combo})

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

def recent_numbers(draws):
    if draws <= 0:
        return set()
    rows = fetch_recent_rows(draws)
    s = set()
    for r in rows:
        for x in r[1:]:
            s.add(x)
    return s

def weighted_pick(pool, weights, k):
    res = []
    items = list(pool)
    ws = [weights.get(x, 1.0) for x in items]
    total_w = sum(ws) or 1.0
    tries = 0
    while len(res) < k and items and tries < 200:
        r = random.random() * total_w
        acc = 0.0
        idx = 0
        for i, w in enumerate(ws):
            acc += w
            if r <= acc:
                idx = i
                break
        choice = items.pop(idx)
        wv = ws.pop(idx)
        total_w -= wv
        res.append(choice)
        tries += 1
    return res

def smart_suggest_conservative(limit):
    ranked = compute_trends(limit)
    order = [n for n, c, ld in ranked]
    evens = [n for n in order if n % 2 == 0]
    odds = [n for n in order if n % 2 == 1]
    pool_even = evens + [n for n in range(1, 50) if n % 2 == 0 and n not in evens]
    pool_odd = odds + [n for n in range(1, 50) if n % 2 == 1 and n not in odds]
    ban = recent_numbers(10)
    tries = 0
    top_k = 12
    while tries < 7000:
        pe = [x for x in pool_even[:top_k] if x not in ban]
        po = [x for x in pool_odd[:top_k] if x not in ban]
        pick_e = []
        pick_o = []
        pe_local = pe[:]
        po_local = po[:]
        while len(pick_e) < 3 and pe_local:
            x = random.choice(pe_local)
            pe_local.remove(x)
            pick_e.append(x)
        while len(pick_o) < 3 and po_local:
            x = random.choice(po_local)
            po_local.remove(x)
            pick_o.append(x)
        cand = sorted(pick_e + pick_o)
        if len(cand) != 6:
            tries += 1
            continue
        if longest_consecutive_run(cand) > 2:
            tries += 1
            continue
        combo = "-".join(str(x) for x in cand)
        if combo in EXISTING:
            tries += 1
            continue
        return cand
    return None

def smart_suggest_exploratory(limit):
    ranked = compute_trends(limit)
    freq = {n: c for n, c, ld in ranked}
    all_freq = {n: freq.get(n, 0.1) for n in range(1, 50)}
    top_k = 25
    tries = 0
    while tries < 8000:
        parity_choice = random.choices([2, 3, 4], weights=[0.25, 0.5, 0.25])[0]
        evens_pool = [n for n in range(1, 50) if n % 2 == 0]
        odds_pool = [n for n in range(1, 50) if n % 2 == 1]
        top_order = [n for n, c, ld in ranked]
        ev_top = [n for n in top_order if n % 2 == 0][:top_k]
        od_top = [n for n in top_order if n % 2 == 1][:top_k]
        ev_pool = ev_top + [n for n in evens_pool if n not in ev_top]
        od_pool = od_top + [n for n in odds_pool if n not in od_top]
        pick_e = weighted_pick(ev_pool, all_freq, parity_choice)
        pick_o = weighted_pick(od_pool, all_freq, 6 - parity_choice)
        cand = sorted(set(pick_e + pick_o))
        if len(cand) != 6:
            tries += 1
            continue
        if longest_consecutive_run(cand) > 3:
            tries += 1
            continue
        combo = "-".join(str(x) for x in cand)
        if combo in EXISTING:
            tries += 1
            continue
        return cand
    return None

def smart_suggest_custom(limit, even_count, max_run, top_k, cooldown, weighted):
    ranked = compute_trends(limit)
    order = [n for n, c, ld in ranked]
    evens = [n for n in order if n % 2 == 0]
    odds = [n for n in order if n % 2 == 1]
    pool_even = evens + [n for n in range(1, 50) if n % 2 == 0 and n not in evens]
    pool_odd = odds + [n for n in range(1, 50) if n % 2 == 1 and n not in odds]
    ban = recent_numbers(cooldown)
    freq = {n: c for n, c, ld in ranked}
    tries = 0
    even_count = max(0, min(6, even_count))
    odd_count = 6 - even_count
    while tries < 8000:
        pe = [x for x in pool_even[:top_k] if x not in ban] if top_k > 0 else [x for x in range(1, 50) if x % 2 == 0 and x not in ban]
        po = [x for x in pool_odd[:top_k] if x not in ban] if top_k > 0 else [x for x in range(1, 50) if x % 2 == 1 and x not in ban]
        if weighted:
            pick_e = weighted_pick(pe, freq, even_count)
            pick_o = weighted_pick(po, freq, odd_count)
        else:
            pick_e = []
            pick_o = []
            pe_local = pe[:]
            po_local = po[:]
            while len(pick_e) < even_count and pe_local:
                x = random.choice(pe_local)
                pe_local.remove(x)
                pick_e.append(x)
            while len(pick_o) < odd_count and po_local:
                x = random.choice(po_local)
                po_local.remove(x)
                pick_o.append(x)
        cand = sorted(set(pick_e + pick_o))
        if len(cand) != 6:
            tries += 1
            continue
        if longest_consecutive_run(cand) > max_run:
            tries += 1
            continue
        combo = "-".join(str(x) for x in cand)
        if combo in EXISTING:
            tries += 1
            continue
        return cand
    return None

@app.route("/update", methods=["GET", "POST"])
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

@app.route("/update.json", methods=["POST"])
def update_json():
    try:
        before = 0
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("select count(*) from mark_six_draws")
        before = cur.fetchone()[0]
        conn.close()
    except Exception:
        before = 0
    try:
        added = incremental_update()
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("select count(*) from mark_six_draws")
        after = cur.fetchone()[0]
        conn.close()
        return jsonify({"ok": True, "added": added, "total": after})
    except Exception as e:
        diag = dns_diagnostics("lottery.hk")
        return jsonify({"ok": False, "error": str(e), "diagnostics": diag}), 500

def existing_draw_numbers():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("select draw_number_text from mark_six_draws")
    s = {r[0] for r in cur.fetchall()}
    conn.close()
    return s

def fetch_html(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        b = r.read()
        return b.decode("utf-8", errors="ignore")

def to_text(html):
    t = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.I)
    t = re.sub(r"<style[\s\S]*?</style>", " ", t, flags=re.I)
    t = re.sub(r"<[^>]+>", " ", t)
    t = unescape(t)
    t = re.sub(r"\s+", " ", t).strip()
    return t

def parse_incremental_draws(text):
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
        window = text[start:start + 1000]
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
    reload_existing()
    return added

def dns_diagnostics(host="lottery.hk"):
    info = {"host": host, "ips": [], "tls_ok": None, "error": None}
    try:
        ais = socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)
        ips = sorted({ai[4][0] for ai in ais})
        info["ips"] = ips
        s = socket.create_connection((host, 443), timeout=5)
        ctx = ssl.create_default_context()
        with ctx.wrap_socket(s, server_hostname=host) as ss:
            ss.settimeout(5)
            info["tls_ok"] = True
    except Exception as e:
        info["error"] = str(e)
    return info

@app.route("/healthz")
def healthz():
    return "OK", 200

@app.route("/health")
def health():
    status = {"app": "ok"}
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("select count(*), max(draw_date) from mark_six_draws")
        count, latest = cur.fetchone()
        cur.execute("select n1,n2,n3,n4,n5,n6 from mark_six_draws")
        rows = cur.fetchall()
        conn.close()
        distinct_draws = count
        distinct_main6 = len({row_to_combo(r) for r in rows})
        status.update({
            "db": "ok",
            "rows": count,
            "distinct_draws": distinct_draws,
            "distinct_main6": distinct_main6,
            "latest_date": latest
        })
        code = 200
    except Exception as e:
        status.update({"db": "error", "error": str(e)})
        code = 500
    return jsonify(status), code

@app.route("/api/number-trend")
def api_number_trend():
    try:
        num = int(request.args.get("num", "1"))
    except Exception:
        return jsonify({"ok": False, "error": "invalid num"}), 400
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        select draw_year,
               sum((n1=?)+(n2=?)+(n3=?)+(n4=?)+(n5=?)+(n6=?)) as main_cnt,
               sum((extra=?)) as extra_cnt
        from mark_six_draws
        where draw_year is not null
        group by draw_year
        order by draw_year
        """,
        (num, num, num, num, num, num, num),
    )
    rows = cur.fetchall()
    conn.close()
    years = [r[0] for r in rows]
    main = [r[1] for r in rows]
    extra = [r[2] for r in rows]
    return jsonify({"ok": True, "years": years, "main": main, "extra": extra, "num": num})

@app.route("/api/number-cooccur")
def api_number_cooccur():
    try:
        num = int(request.args.get("num", "1"))
    except Exception:
        return jsonify({"ok": False, "error": "invalid num"}), 400
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        select n1,n2,n3,n4,n5,n6 from mark_six_draws
        where ? in (n1,n2,n3,n4,n5,n6)
        """,
        (num,),
    )
    rows = cur.fetchall()
    conn.close()
    counts = {i: 0 for i in range(1, 50)}
    for r in rows:
        for x in r:
            if x != num:
                counts[x] += 1
    pairs = sorted(([k, v] for k, v in counts.items() if k != num and v > 0), key=lambda t: (-t[1], t[0]))[:10]
    return jsonify({"ok": True, "num": num, "pairs": [{"n": p[0], "count": p[1]} for p in pairs]})

@app.route("/api/color-totals")
def api_color_totals():
    rows = fetch_all_numbers()
    totals = {"red": 0, "blue": 0, "green": 0}
    for r in rows:
        for x in r:
            c = ball_color(x)
            if c in totals:
                totals[c] += 1
    return jsonify({"ok": True, "totals": totals, "draws": len(rows)})

@app.route("/api/color-by-year")
def api_color_by_year():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("select draw_year, n1,n2,n3,n4,n5,n6 from mark_six_draws where draw_year is not null")
    buckets = {}
    for row in cur.fetchall():
        y = int(row[0])
        nums = row[1:]
        if y not in buckets:
            buckets[y] = {"red": 0, "blue": 0, "green": 0}
        for x in nums:
            c = ball_color(x)
            if c in buckets[y]:
                buckets[y][c] += 1
    conn.close()
    years = sorted(buckets.keys())
    red = [buckets[y]["red"] for y in years]
    blue = [buckets[y]["blue"] for y in years]
    green = [buckets[y]["green"] for y in years]
    return jsonify({"ok": True, "years": years, "red": red, "blue": blue, "green": green})

@app.route("/api/rare/same-decade")
def api_rare_same_decade():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("select draw_number_text, draw_date, n1,n2,n3,n4,n5,n6 from mark_six_draws order by draw_date")
    rows = cur.fetchall()
    conn.close()
    out = []
    for r in rows:
        nums = [r[2], r[3], r[4], r[5], r[6], r[7]]
        decs = {(n - 1) // 10 for n in nums}
        if len(decs) == 1:
            dec = list(decs)[0]
            out.append({
                "draw": r[0],
                "date": r[1],
                "numbers": sorted(nums),
                "decade": f"{dec * 10}-{dec * 10 + 9}"
            })
    return jsonify({"ok": True, "items": out})

@app.route("/diag")
def diag():
    host = request.args.get("host", "lottery.hk")
    return jsonify(dns_diagnostics(host))

@app.route("/api/suggest", methods=["POST"])
def api_suggest():
    tries = 0
    while tries < 5000:
        pick = sorted(random.sample(range(1, 50), 6))
        combo = "-".join(str(x) for x in pick)
        if combo not in EXISTING:
            return jsonify({"ok": True, "suggestion": pick})
        tries += 1
    return jsonify({"ok": False, "error": "no unique combination found"}), 500

@app.route("/api/smart_unified", methods=["POST"])
def api_smart_unified():
    preset = request.form.get("preset", "default")
    def read_int(name, default):
        try:
            return int(request.form.get(name) or default)
        except ValueError:
            return default
    w = read_int("window", 200)
    label = None
    if preset == "default":
        res = smart_suggest(w)
        label = "Smart (default)"
    elif preset == "conservative":
        res = smart_suggest_conservative(w)
        label = "Smart (conservative)"
    elif preset == "exploratory":
        res = smart_suggest_exploratory(w)
        label = "Smart (exploratory)"
    else:
        even_count = read_int("even_count", 3)
        max_run = read_int("max_run", 2)
        top_k = read_int("top_k", 15)
        cooldown = read_int("cooldown", 0)
        weighted = True if request.form.get("weighted") == "on" else False
        res = smart_suggest_custom(w, even_count, max_run, top_k, cooldown, weighted)
        label = f"Custom (even={even_count}, run≤{max_run})"
    if res is None:
        return jsonify({"ok": False, "error": "no suggestion"}), 500
    return jsonify({"ok": True, "smart": res, "label": label})

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8000, debug=True)
