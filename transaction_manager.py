"""
Transaction Manager for DigiCal
Handles sales and expense tracking
"""
from datetime import datetime, timedelta
from database import Database

class TransactionManager:
    def __init__(self, db):
        self.db = db
    
    def add_sale(self, amount, category, description="", payment_method="Cash", handler_id=None, date=None):
        """Add a sales transaction"""
        return self.db.add_transaction('sales', amount, category, description, payment_method, handler_id, date)
    
    def add_expense(self, amount, category, description="", payment_method="Cash", handler_id=None, date=None):
        """Add an expense transaction"""
        return self.db.add_transaction('expense', amount, category, description, payment_method, handler_id, date)
    
    def get_sales(self, start_date=None, end_date=None):
        """Get all sales transactions"""
        return self.db.get_transactions('sales', start_date, end_date)
    
    def get_expenses(self, start_date=None, end_date=None):
        """Get all expense transactions"""
        return self.db.get_transactions('expense', start_date, end_date)
    
    def get_all_transactions(self, start_date=None, end_date=None):
        """Get all transactions"""
        return self.db.get_transactions(None, start_date, end_date)
    
    def get_summary(self, start_date=None, end_date=None):
        """Get summary of sales and expenses"""
        sales = self.get_sales(start_date, end_date)
        expenses = self.get_expenses(start_date, end_date)
        
        total_sales = sum(trans[2] for trans in sales)  # amount is at index 2
        total_expenses = sum(trans[2] for trans in expenses)
        profit = total_sales - total_expenses
        
        return {
            'total_sales': total_sales,
            'total_expenses': total_expenses,
            'profit': profit,
            'sales_count': len(sales),
            'expenses_count': len(expenses)
        }
    
    def get_daily_summary(self, date=None):
        """Get summary for a specific day"""
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")
        return self.get_summary(date, date)
    
    def get_weekly_summary(self):
        """Get summary for the current week"""
        today = datetime.now()
        start_of_week = today - timedelta(days=today.weekday())
        start_date = start_of_week.strftime("%Y-%m-%d")
        end_date = today.strftime("%Y-%m-%d")
        return self.get_summary(start_date, end_date)
    
    def get_monthly_summary(self, year=None, month=None):
        """Get summary for a specific month"""
        if year is None or month is None:
            today = datetime.now()
            year = today.year
            month = today.month
        
        start_date = f"{year}-{month:02d}-01"
        
        # Calculate last day of month
        if month == 12:
            next_month = f"{year+1}-01-01"
        else:
            next_month = f"{year}-{month+1:02d}-01"
        
        last_day = (datetime.strptime(next_month, "%Y-%m-%d") - timedelta(days=1)).day
        end_date = f"{year}-{month:02d}-{last_day:02d}"
        
        return self.get_summary(start_date, end_date)
    
    def get_category_breakdown(self, trans_type, start_date=None, end_date=None):
        """Get breakdown by category"""
        transactions = self.db.get_transactions(trans_type, start_date, end_date)
        
        breakdown = {}
        for trans in transactions:
            category = trans[3]  # category is at index 3
            amount = trans[2]    # amount is at index 2
            
            if category in breakdown:
                breakdown[category] += amount
            else:
                breakdown[category] = amount
        
        return breakdown
    
    def get_payment_method_breakdown(self, trans_type=None, start_date=None, end_date=None):
        """Get breakdown by payment method"""
        transactions = self.db.get_transactions(trans_type, start_date, end_date)
        
        breakdown = {}
        for trans in transactions:
            payment_method = trans[5] if len(trans) > 5 and trans[5] else "Cash"  # payment_method at index 5
            amount = trans[2]  # amount is at index 2
            
            if payment_method in breakdown:
                breakdown[payment_method] += amount
            else:
                breakdown[payment_method] = amount
        
        return breakdown
    
    def get_sales_categories(self):
        """Get all sales categories"""
        categories = self.db.get_categories('sales')
        return [cat[0] for cat in categories]
    
    def get_expense_categories(self):
        """Get all expense categories"""
        categories = self.db.get_categories('expense')
        return [cat[0] for cat in categories]
    
    def add_category(self, name, cat_type):
        """Add a new category"""
        return self.db.add_category(name, cat_type)
