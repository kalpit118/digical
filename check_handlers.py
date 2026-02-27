"""
Check if any transactions have handler_id set
"""
import sqlite3

conn = sqlite3.connect('digical.db')
cursor = conn.cursor()

# Check transactions with handler_id
cursor.execute("SELECT COUNT(*) FROM transactions WHERE handler_id IS NOT NULL")
count_with_handler = cursor.fetchone()[0]

cursor.execute("SELECT COUNT(*) FROM transactions")
total_count = cursor.fetchone()[0]

print(f"Total transactions: {total_count}")
print(f"Transactions with handler_id: {count_with_handler}")
print(f"Transactions without handler_id: {total_count - count_with_handler}")

# Check if there are any handlers
cursor.execute("SELECT id, name FROM handlers")
handlers = cursor.fetchall()
print(f"\nAvailable handlers: {len(handlers)}")
for h_id, h_name in handlers:
    print(f"  - {h_name} (ID: {h_id})")

conn.close()
