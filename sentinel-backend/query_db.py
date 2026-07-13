import sqlite3

conn = sqlite3.connect("kavach.db")
c = conn.cursor()

# Get latest snapshot values for MSME00231 to understand where it stands
snap = c.execute("""
    SELECT dpd_current, dscr, bureau_score 
    FROM monthly_snapshots 
    WHERE borrower_id = 'MSME00231' 
    ORDER BY month_index DESC 
    LIMIT 1
""").fetchone()

print("MSME00231 Current Snap:", snap)

conn.close()
