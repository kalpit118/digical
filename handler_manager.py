"""
Handler Manager for DigiCal
Manages calculator handlers and their incentive calculations
"""
from database import Database

class HandlerManager:
    def __init__(self, db):
        self.db = db
        self.current_handler = None
        self.load_active_handler()
    
    def load_active_handler(self):
        """Load the currently active handler from database"""
        handler = self.db.get_active_handler()
        if handler:
            self.current_handler = {
                'id': handler[0],
                'name': handler[1],
                'incentive_percentage': handler[2],
                'incentive_type': handler[3]
            }
        else:
            self.current_handler = None
    
    def create_handler(self, name, incentive_percentage, incentive_type='percentage'):
        """Create a new handler and set as active"""
        success, handler_id = self.db.add_handler(name, incentive_percentage, incentive_type)
        if success:
            self.set_current_handler(handler_id)
        return success
    
    def get_handler_list(self):
        """Get list of all handlers"""
        handlers = self.db.get_handlers()
        return [(h[0], h[1], h[2], h[3]) for h in handlers]  # (id, name, incentive_percentage, incentive_type)
    
    def set_current_handler(self, handler_id):
        """Set a handler as the current active handler"""
        self.db.set_active_handler(handler_id)
        self.load_active_handler()
    
    def get_current_handler(self):
        """Get the current active handler"""
        return self.current_handler
    
    def calculate_incentive(self, amount):
        """Calculate incentive for the current handler based on amount"""
        if not self.current_handler:
            return 0
        
        try:
            amount_val = float(amount)
            incentive_type = self.current_handler.get('incentive_type', 'percentage')
            incentive_value = self.current_handler['incentive_percentage']
            
            if incentive_type == 'fixed':
                # Fixed amount per transaction
                incentive = incentive_value
            else:
                # Percentage of transaction amount
                incentive = amount_val * (incentive_value / 100)
            
            return round(incentive, 2)
        except (ValueError, TypeError):
            return 0
    
    def get_handler_performance(self):
        """Get performance data for all handlers"""
        return self.db.get_all_handler_incentives()
    
    def get_handler_name(self, handler_id):
        """Get handler name by ID"""
        handlers = self.db.get_handlers()
        for h in handlers:
            if h[0] == handler_id:
                return h[1]
        return "Unknown"
