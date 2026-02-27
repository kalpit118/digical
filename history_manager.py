"""
History Manager for DigiCal
Manages calculation and transaction history
"""
from database import Database

class HistoryManager:
    def __init__(self, db):
        self.db = db
    
    def add_calculation(self, expression, result):
        """Add a calculation to history"""
        self.db.add_calculation(expression, result)
    
    def get_calculation_history(self, limit=50):
        """Get calculation history"""
        return self.db.get_calculations(limit)
    
    def get_transaction_history(self, trans_type=None, limit=50):
        """Get transaction history"""
        transactions = self.db.get_transactions(trans_type)
        return transactions[:limit]
    
    def clear_calculation_history(self):
        """Clear all calculation history"""
        self.db.clear_history('calculations')
    
    def clear_transaction_history(self):
        """Clear all transaction history"""
        self.db.clear_history('transactions')
    
    def search_transactions(self, keyword, trans_type=None):
        """Search transactions by description or category"""
        all_transactions = self.db.get_transactions(trans_type)
        
        # Filter by keyword in description or category
        keyword_lower = keyword.lower()
        filtered = [
            trans for trans in all_transactions
            if keyword_lower in trans[3].lower() or  # category
               (trans[4] and keyword_lower in trans[4].lower())  # description
        ]
        
        return filtered
    
    def format_calculation_history(self):
        """Format calculation history for display"""
        history = self.get_calculation_history()
        formatted = []
        
        for expr, result, timestamp in history:
            formatted.append(f"{timestamp}: {expr} = {result}")
        
        return formatted
    
    def format_transaction_history(self, trans_type=None):
        """Format transaction history for display"""
        history = self.get_transaction_history(trans_type)
        formatted = []
        
        for trans in history:
            # trans structure from JOIN query: 
            # id, type, amount, category, description, date, created_at, payment_method, handler_id, handler_name
            trans_id = trans[0]
            t_type = trans[1]
            amount = trans[2]
            category = trans[3]
            description = trans[4] if len(trans) > 4 and trans[4] else ""
            date = trans[5] if len(trans) > 5 else ""
            created_at = trans[6] if len(trans) > 6 else ""
            payment_method = trans[7] if len(trans) > 7 and trans[7] else "Cash"
            handler_id = trans[8] if len(trans) > 8 else None
            handler_name = trans[9] if len(trans) > 9 and trans[9] else None
            
            type_symbol = "+" if t_type == "sales" else "-"
            desc_text = f" ({description})" if description else ""
            payment_text = f" [{payment_method}]" if payment_method else ""
            handler_text = f" | Handler: {handler_name}" if handler_name else ""
            
            formatted.append(f"{date}: {type_symbol}₹{amount:.2f} - {category}{desc_text}{payment_text}{handler_text}")
        
        return formatted
