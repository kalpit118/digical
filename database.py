"""
Database Manager for DigiCal
Handles SQLite database operations for transactions, calculations, and categories
"""
import sqlite3
from datetime import datetime
import config

class Database:
    def __init__(self, db_path=config.DB_PATH):
        self.db_path = db_path
        self.init_database()
    
    def get_connection(self):
        """Create and return a database connection"""
        return sqlite3.connect(self.db_path)
    
    def init_database(self):
        """Initialize database tables"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Transactions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT NOT NULL,
                amount REAL NOT NULL,
                category TEXT NOT NULL,
                description TEXT,
                payment_method TEXT,
                handler_id INTEGER,
                date TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (handler_id) REFERENCES handlers(id)
            )
        ''')
        
        # Calculations history table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS calculations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                expression TEXT NOT NULL,
                result TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                handler_id INTEGER,
                handler_incentive REAL DEFAULT 0,
                FOREIGN KEY (handler_id) REFERENCES handlers(id)
            )
        ''')
        
        # Handlers table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS handlers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                incentive_percentage REAL NOT NULL,
                incentive_type TEXT DEFAULT 'percentage',
                created_at TEXT NOT NULL,
                is_active INTEGER DEFAULT 0
            )
        ''')
        
        # Customers table (for Due payment method)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS customers (
                customer_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                phone TEXT,
                email TEXT,
                created_at TEXT NOT NULL
            )
        ''')
        
        # Due records table (links Due-payment transactions to customers)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS due_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                transaction_id INTEGER NOT NULL,
                customer_id TEXT NOT NULL,
                amount REAL NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (transaction_id) REFERENCES transactions(id),
                FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
            )
        ''')
        
        # Settlements table (records partial/full due payments)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS settlements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id TEXT NOT NULL,
                amount REAL NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
            )
        ''')
        
        # Products (inventory) table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                total_qty REAL NOT NULL DEFAULT 0,
                left_qty REAL NOT NULL DEFAULT 0,
                price REAL NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        ''')
        
        # Categories table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                type TEXT NOT NULL
            )
        ''')
        
        # Initialize default categories if empty
        cursor.execute('SELECT COUNT(*) FROM categories')
        if cursor.fetchone()[0] == 0:
            for cat in config.DEFAULT_SALES_CATEGORIES:
                cursor.execute('INSERT INTO categories (name, type) VALUES (?, ?)', 
                             (cat, 'sales'))
            for cat in config.DEFAULT_EXPENSE_CATEGORIES:
                cursor.execute('INSERT INTO categories (name, type) VALUES (?, ?)', 
                             (cat, 'expense'))
        
        # Migration: Add payment_method column if it doesn't exist
        cursor.execute("PRAGMA table_info(transactions)")
        columns = [column[1] for column in cursor.fetchall()]
        if 'payment_method' not in columns:
            cursor.execute('ALTER TABLE transactions ADD COLUMN payment_method TEXT DEFAULT "Cash"')
            print("Database migrated: Added payment_method column")
        if 'handler_id' not in columns:
            cursor.execute('ALTER TABLE transactions ADD COLUMN handler_id INTEGER')
            print("Database migrated: Added handler_id column to transactions")
        
        # Migration: Add handler columns to calculations table if they don't exist
        cursor.execute("PRAGMA table_info(calculations)")
        calc_columns = [column[1] for column in cursor.fetchall()]
        if 'handler_id' not in calc_columns:
            cursor.execute('ALTER TABLE calculations ADD COLUMN handler_id INTEGER')
            print("Database migrated: Added handler_id column to calculations")
        if 'handler_incentive' not in calc_columns:
            cursor.execute('ALTER TABLE calculations ADD COLUMN handler_incentive REAL DEFAULT 0')
            print("Database migrated: Added handler_incentive column to calculations")
        
        # Migration: Add incentive_type column to handlers table if it doesn't exist
        cursor.execute("PRAGMA table_info(handlers)")
        handler_columns = [column[1] for column in cursor.fetchall()]
        if 'incentive_type' not in handler_columns:
            cursor.execute('ALTER TABLE handlers ADD COLUMN incentive_type TEXT DEFAULT "percentage"')
            print("Database migrated: Added incentive_type column to handlers")
        
        conn.commit()
        conn.close()
    
    def add_transaction(self, trans_type, amount, category, description="", payment_method="Cash", handler_id=None, date=None):
        """Add a new transaction"""
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO transactions (type, amount, category, description, payment_method, handler_id, date, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (trans_type, amount, category, description, payment_method, handler_id, date, created_at))
        conn.commit()
        trans_id = cursor.lastrowid
        conn.close()
        return trans_id
    
    def get_transactions(self, trans_type=None, start_date=None, end_date=None):
        """Retrieve transactions with optional filters"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        query = '''
            SELECT t.*, h.name as handler_name 
            FROM transactions t
            LEFT JOIN handlers h ON t.handler_id = h.id
            WHERE 1=1
        '''
        params = []
        
        if trans_type:
            query += ' AND t.type = ?'
            params.append(trans_type)
        if start_date:
            query += ' AND t.date >= ?'
            params.append(start_date)
        if end_date:
            query += ' AND t.date <= ?'
            params.append(end_date)
        
        query += ' ORDER BY t.date DESC, t.created_at DESC'
        
        cursor.execute(query, params)
        transactions = cursor.fetchall()
        conn.close()
        return transactions
    
    def add_calculation(self, expression, result, handler_id=None, handler_incentive=0):
        """Add calculation to history"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO calculations (expression, result, timestamp, handler_id, handler_incentive)
            VALUES (?, ?, ?, ?, ?)
        ''', (expression, result, timestamp, handler_id, handler_incentive))
        conn.commit()
        conn.close()
    
    def get_calculations(self, limit=config.MAX_HISTORY_ITEMS):
        """Retrieve calculation history"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT expression, result, timestamp FROM calculations
            ORDER BY timestamp DESC LIMIT ?
        ''', (limit,))
        calculations = cursor.fetchall()
        conn.close()
        return calculations
    
    def get_categories(self, cat_type=None):
        """Get categories, optionally filtered by type"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if cat_type:
            cursor.execute('SELECT name FROM categories WHERE type = ? ORDER BY name', (cat_type,))
        else:
            cursor.execute('SELECT name, type FROM categories ORDER BY type, name')
        
        categories = cursor.fetchall()
        conn.close()
        return categories
    
    def add_category(self, name, cat_type):
        """Add a new category"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('INSERT INTO categories (name, type) VALUES (?, ?)', (name, cat_type))
            conn.commit()
            success = True
        except sqlite3.IntegrityError:
            success = False
        conn.close()
        return success
    
    def clear_history(self, history_type='calculations'):
        """Clear calculation or transaction history"""
        conn = self.get_connection()
        cursor = conn.cursor()
        if history_type == 'calculations':
            cursor.execute('DELETE FROM calculations')
        elif history_type == 'transactions':
            cursor.execute('DELETE FROM transactions')
        conn.commit()
        conn.close()
    
    # Handler Management Methods
    def add_handler(self, name, incentive_percentage, incentive_type='percentage'):
        """Add a new handler"""
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO handlers (name, incentive_percentage, incentive_type, created_at, is_active)
                VALUES (?, ?, ?, ?, 0)
            ''', (name, incentive_percentage, incentive_type, created_at))
            conn.commit()
            handler_id = cursor.lastrowid
            success = True
        except sqlite3.IntegrityError:
            handler_id = None
            success = False
        conn.close()
        return (success, handler_id)
    
    def get_handlers(self):
        """Get all handlers"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT id, name, incentive_percentage, incentive_type, is_active FROM handlers ORDER BY name')
        handlers = cursor.fetchall()
        conn.close()
        return handlers
    
    def get_active_handler(self):
        """Get the currently active handler"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT id, name, incentive_percentage, incentive_type FROM handlers WHERE is_active = 1 LIMIT 1')
        handler = cursor.fetchone()
        conn.close()
        return handler
    
    def set_active_handler(self, handler_id):
        """Set a handler as active (deactivates all others)"""
        conn = self.get_connection()
        cursor = conn.cursor()
        # Deactivate all handlers
        cursor.execute('UPDATE handlers SET is_active = 0')
        # Activate the selected handler
        cursor.execute('UPDATE handlers SET is_active = 1 WHERE id = ?', (handler_id,))
        conn.commit()
        conn.close()
    
    def get_handler_total_incentives(self, handler_id):
        """Get total incentives earned by a handler"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT SUM(handler_incentive) FROM calculations 
            WHERE handler_id = ?
        ''', (handler_id,))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result[0] else 0
    
    def get_all_handler_incentives(self):
        """Get total incentives for all handlers"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT h.id, h.name, COALESCE(SUM(c.handler_incentive), 0) as total_incentive
            FROM handlers h
            LEFT JOIN calculations c ON h.id = c.handler_id
            GROUP BY h.id, h.name
            ORDER BY total_incentive DESC
        ''')
        results = cursor.fetchall()
        conn.close()
        return results

    def get_handlers_performance(self):
        """Alias for get_all_handler_incentives to be used by graphs"""
        return self.get_all_handler_incentives()
    
    # Customer Management Methods
    def add_customer(self, name, phone, email=None):
        """Add a new customer with an auto-generated ID (starting at 1000).
        Returns (customer_id, error_msg) — customer_id is None on failure."""
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = self.get_connection()
        cursor = conn.cursor()
        # Compute next ID
        cursor.execute('SELECT MAX(CAST(customer_id AS INTEGER)) FROM customers')
        row = cursor.fetchone()
        next_id = str((row[0] + 1) if row[0] and row[0] >= 1000 else 1000)
        try:
            cursor.execute(
                'INSERT INTO customers (customer_id, name, phone, email, created_at) VALUES (?, ?, ?, ?, ?)',
                (next_id, name.strip(), phone.strip(), email.strip() if email else None, created_at)
            )
            conn.commit()
            result, error = next_id, None
        except sqlite3.IntegrityError as e:
            result, error = None, str(e)
        conn.close()
        return result, error
    
    def get_customer_by_id(self, customer_id):
        """Fetch a customer by their ID."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            'SELECT customer_id, name, phone, email FROM customers WHERE customer_id = ?',
            (customer_id.strip(),)
        )
        row = cursor.fetchone()
        conn.close()
        return row
    
    def get_customer_by_phone(self, phone):
        """Fetch a customer by phone number."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            'SELECT customer_id, name, phone, email FROM customers WHERE phone = ?',
            (phone.strip(),)
        )
        row = cursor.fetchone()
        conn.close()
        return row
    
    def update_customer(self, customer_id, name, phone, email=None):
        """Update an existing customer's details."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            'UPDATE customers SET name=?, phone=?, email=? WHERE customer_id=?',
            (name.strip(), phone.strip(), email.strip() if email else None, customer_id)
        )
        conn.commit()
        conn.close()
    
    def get_all_customers(self):
        """Return all customers ordered by customer_id."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT customer_id, name, phone, email FROM customers ORDER BY CAST(customer_id AS INTEGER)')
        rows = cursor.fetchall()
        conn.close()
        return rows
    
    def get_customers_with_dues(self):
        """Return customers with their total net unsettled due amount."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT c.customer_id, c.name, c.phone,
                   COALESCE((SELECT SUM(d.amount) FROM due_records d WHERE d.customer_id = c.customer_id), 0)
                   - COALESCE((SELECT SUM(s.amount) FROM settlements s WHERE s.customer_id = c.customer_id), 0)
                   as total_due
            FROM customers c
            ORDER BY CAST(c.customer_id AS INTEGER)
        ''')
        rows = cursor.fetchall()
        conn.close()
        return rows
    
    def get_next_customer_id(self):
        """Return the next auto-generated customer ID (preview, does not insert)."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT MAX(CAST(customer_id AS INTEGER)) FROM customers')
        row = cursor.fetchone()
        conn.close()
        return str((row[0] + 1) if row[0] and row[0] >= 1000 else 1000)
    
    def add_settlement(self, customer_id, amount):
        """Record a due settlement for a customer."""
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO settlements (customer_id, amount, created_at) VALUES (?, ?, ?)',
            (customer_id, amount, created_at)
        )
        conn.commit()
        conn.close()
    
    def add_due_record(self, transaction_id, customer_id, amount):
        """Record a due-payment link between a transaction and a customer."""
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO due_records (transaction_id, customer_id, amount, created_at) VALUES (?, ?, ?, ?)',
            (transaction_id, customer_id, amount, created_at)
        )
        conn.commit()
        conn.close()
    
    # ── Product Management Methods ──────────────────────────────────────────
    def add_product(self, name, category, total_qty, price, left_qty=None):
        """Add a new product. left_qty defaults to total_qty."""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if left_qty is None:
            left_qty = total_qty
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO products (name, category, total_qty, left_qty, price, created_at, updated_at)'
            ' VALUES (?, ?, ?, ?, ?, ?, ?)',
            (name.strip(), category, float(total_qty), float(left_qty), float(price), now, now)
        )
        conn.commit()
        product_id = cursor.lastrowid
        conn.close()
        return product_id
    
    def get_products(self):
        """Return all products ordered by id."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            'SELECT id, name, category, total_qty, left_qty, price FROM products ORDER BY id'
        )
        rows = cursor.fetchall()
        conn.close()
        return rows
    
    def get_product(self, product_id):
        """Return a single product by id."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            'SELECT id, name, category, total_qty, left_qty, price FROM products WHERE id = ?',
            (product_id,)
        )
        row = cursor.fetchone()
        conn.close()
        return row
    
    def update_product(self, product_id, name, category, total_qty, left_qty, price):
        """Update an existing product."""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            'UPDATE products SET name=?, category=?, total_qty=?, left_qty=?, price=?, updated_at=?'
            ' WHERE id=?',
            (name.strip(), category, float(total_qty), float(left_qty), float(price), now, product_id)
        )
        conn.commit()
        conn.close()
    
    def delete_product(self, product_id):
        """Delete a product by id."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM products WHERE id = ?', (product_id,))
        conn.commit()
        conn.close()
