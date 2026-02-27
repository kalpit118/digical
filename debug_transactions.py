"""
Debug script to check transaction data structure
"""
from database import Database

db = Database()
transactions = db.get_transactions()

if transactions:
    print(f"Number of transactions: {len(transactions)}")
    print(f"\nFirst transaction structure:")
    first = transactions[0]
    print(f"Length: {len(first)}")
    print(f"Data: {first}")
    print(f"\nField breakdown:")
    for i, field in enumerate(first):
        print(f"  Index {i}: {field}")
else:
    print("No transactions found")
