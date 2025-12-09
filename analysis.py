import os
import sqlite3

DB_PATH = os.path.join("data", "mark_six.sqlite")

def fetch_rows():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("select n1,n2,n3,n4,n5,n6 from mark_six_draws")
    rows = cur.fetchall()
    conn.close()
    return rows

def longest_run(nums):
    s = sorted(nums)
    best = 1
    cur = 1
    for i in range(1, len(s)):
        if s[i] == s[i-1] + 1:
            cur += 1
            best = max(best, cur)
        elif s[i] != s[i-1]:
            cur = 1
    return best

def main():
    rows = fetch_rows()
    total = len(rows)
    parity_counts = {k: 0 for k in range(7)}
    run_counts = {k: 0 for k in range(1, 7)}
    same_decade_all = 0
    last_digit_all = 0
    for r in rows:
        ev = sum(1 for x in r if x % 2 == 0)
        parity_counts[ev] += 1
        run_counts[longest_run(r)] += 1
        decs = {(x - 1) // 10 for x in r}
        if len(decs) == 1:
            same_decade_all += 1
        if len({x % 10 for x in r}) == 1:
            last_digit_all += 1
    print({
        "total": total,
        "parity_counts": parity_counts,
        "run_counts": run_counts,
        "same_decade_all": same_decade_all,
        "last_digit_all": last_digit_all,
    })

if __name__ == "__main__":
    main()

