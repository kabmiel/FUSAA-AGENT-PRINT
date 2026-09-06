import sqlite3
db = sqlite3.connect('backend/fusaa.db')
tables = db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
print("=== TABLES ===")
for t in tables:
    print(" ", t[0])

print("\n=== computer_agents ===")
try:
    rows = db.execute("SELECT id, name, status, workshop_id FROM computer_agents LIMIT 5").fetchall()
    for r in rows:
        print(" ", r)
except Exception as e:
    print("  ERROR:", e)

print("\n=== print_jobs ===")
try:
    rows = db.execute("SELECT id, status, workshop_id FROM print_jobs LIMIT 5").fetchall()
    for r in rows:
        print(" ", r)
except Exception as e:
    print("  ERROR:", e)

print("\n=== users ===")
try:
    rows = db.execute("SELECT id, email, is_active FROM users LIMIT 5").fetchall()
    for r in rows:
        print(" ", r)
except Exception as e:
    print("  ERROR:", e)

print("\n=== browser_links ===")
try:
    rows = db.execute("SELECT id, enabled, workshop_id FROM browser_links LIMIT 5").fetchall()
    for r in rows:
        print(" ", r)
except Exception as e:
    print("  ERROR:", e)
