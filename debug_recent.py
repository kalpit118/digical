"""
Debug: Check actual transaction data with handler info
"""
import sqlite3

conn = sqlite3.connect('digical.db')
cursor = conn.cursor()

# Get the most recent transaction with full details
cursor.execute('''
    SELECT t.*, h.name as handler_name 
    FROM transactions t
    LEFT JOIN handlers h ON t.handler_id = h.id
    ORDER BY t.created_at DESC
    LIMIT 3
''')

print("Most recent transactions with JOIN:")
print("="*80)
results = cursor.fetchall()
for row in results:
    print(f"\nTransaction ID: {row[0]}")
    print(f"  Type: {row[1]}")
    print(f"  Amount: {row[2]}")
    print(f"  Category: {row[3]}")
    print(f"  Description: {row[4]}")
    print(f"  Date: {row[5]}")
    print(f"  Created: {row[6]}")
    print(f"  Payment: {row[7]}")
    print(f"  Handler ID: {row[8]}")
    print(f"  Handler Name: {row[9]}")
    print(f"  Full row length: {len(row)}")

conn.close()
