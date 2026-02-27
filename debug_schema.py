"""
Debug script to check actual column order from database
"""
import sqlite3

conn = sqlite3.connect('digical.db')
cursor = conn.cursor()

# Get table schema
cursor.execute("PRAGMA table_info(transactions)")
columns = cursor.fetchall()

print("Transactions table schema:")
for col in columns:
    print(f"  Index {col[0]}: {col[1]} ({col[2]})")

print("\n" + "="*50 + "\n")

# Get a sample transaction with JOIN
cursor.execute('''
    SELECT t.*, h.name as handler_name 
    FROM transactions t
    LEFT JOIN handlers h ON t.handler_id = h.id
    LIMIT 1
''')

result = cursor.fetchone()
if result:
    print(f"Sample transaction (length: {len(result)}):")
    for i, val in enumerate(result):
        print(f"  Index {i}: {val}")
else:
    print("No transactions found")

conn.close()
