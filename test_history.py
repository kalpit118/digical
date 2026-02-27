"""
Test transaction history formatting
"""
from database import Database
from history_manager import HistoryManager

db = Database()
history_mgr = HistoryManager(db)

print("Testing transaction history formatting:\n")
print("="*70)

formatted = history_mgr.format_transaction_history()

if formatted:
    print(f"Found {len(formatted)} transactions:\n")
    for i, line in enumerate(formatted[:5], 1):  # Show first 5
        print(f"{i}. {line}")
else:
    print("No transactions found")

print("\n" + "="*70)
print("\nChecking if handler names appear:")
has_handler = any("Handler:" in line for line in formatted)
print(f"Handler names present: {has_handler}")
