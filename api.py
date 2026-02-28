"""
Flask REST API for DigiCal Web Portal
Exposes business data and analytics as JSON endpoints
"""
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from datetime import datetime, timedelta
from database import Database
from transaction_manager import TransactionManager
from handler_manager import HandlerManager
import config
import os

app = Flask(__name__, static_folder='web', static_url_path='')
CORS(app)  # Enable CORS for all routes

# Initialize components
db = Database()
transaction_manager = TransactionManager(db)
handler_manager = HandlerManager(db)



@app.route('/')
def index():
    """Serve the web portal"""
    return send_from_directory('web', 'index.html')


@app.route('/web')
def web_portal():
    """Redirect to main page"""
    return send_from_directory('web', 'index.html')


@app.route('/api')
def api_info():
    """API information page"""
    return """
    <html>
    <head><title>DigiCal API</title></head>
    <body style="font-family: Arial; padding: 40px; background: #1a1a2e; color: white;">
        <h1>DigiCal API Server</h1>
        <p>API is running! Access the web portal at <a href="/" style="color: #4CAF50;">Home</a></p>
        <h2>Available Endpoints:</h2>
        <ul>
            <li><a href="/api/summary" style="color: #2196F3;">/api/summary</a> - Business summary</li>
            <li><a href="/api/transactions" style="color: #2196F3;">/api/transactions</a> - Transaction history</li>
            <li><a href="/api/calculations" style="color: #2196F3;">/api/calculations</a> - Calculation history</li>
            <li><a href="/api/handlers" style="color: #2196F3;">/api/handlers</a> - Handler data</li>
            <li><a href="/api/graphs/weekly" style="color: #2196F3;">/api/graphs/weekly</a> - Weekly chart data</li>
            <li><a href="/api/graphs/monthly" style="color: #2196F3;">/api/graphs/monthly</a> - Monthly trend data</li>
            <li><a href="/api/graphs/categories/sales" style="color: #2196F3;">/api/graphs/categories/sales</a> - Sales breakdown</li>
            <li><a href="/api/graphs/categories/expense" style="color: #2196F3;">/api/graphs/categories/expense</a> - Expense breakdown</li>
            <li><a href="/api/graphs/profit" style="color: #2196F3;">/api/graphs/profit</a> - Profit trend</li>
        </ul>
    </body>
    </html>
    """



@app.route('/api/summary')
def get_summary():
    """Get business summary (daily, weekly, monthly)"""
    try:
        daily = transaction_manager.get_daily_summary()
        weekly = transaction_manager.get_weekly_summary()
        monthly = transaction_manager.get_monthly_summary()
        
        # Get current handler
        current_handler = handler_manager.get_current_handler()
        handler_info = None
        if current_handler:
            handler_info = {
                'id': current_handler['id'],
                'name': current_handler['name'],
                'incentive': current_handler['incentive_percentage'],
                'type': current_handler['incentive_type']
            }
        
        return jsonify({
            'success': True,
            'data': {
                'daily': daily,
                'weekly': weekly,
                'monthly': monthly,
                'current_handler': handler_info,
                'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/transactions')
def get_transactions():
    """Get transaction history with optional filters"""
    try:
        trans_type = request.args.get('type')  # 'sales' or 'expense'
        limit = int(request.args.get('limit', 50))
        
        transactions = db.get_transactions(trans_type=trans_type)
        
        # Format transactions
        formatted = []
        for t in transactions[:limit]:
            formatted.append({
                'id': t[0],
                'type': t[1],
                'amount': t[2],
                'category': t[3],
                'description': t[4],
                'date': t[5],
                'created_at': t[6],
                'payment_method': t[7],
                'handler_id': t[8],
                'handler_name': t[9] if len(t) > 9 else None
            })
        
        return jsonify({
            'success': True,
            'data': formatted,
            'count': len(formatted)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/calculations')
def get_calculations():
    """Get calculation history"""
    try:
        limit = int(request.args.get('limit', 50))
        calculations = db.get_calculations(limit=limit)
        
        formatted = []
        for c in calculations:
            formatted.append({
                'expression': c[0],
                'result': c[1],
                'timestamp': c[2]
            })
        
        return jsonify({
            'success': True,
            'data': formatted,
            'count': len(formatted)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/handlers')
def get_handlers():
    """Get handler performance data"""
    try:
        handlers = handler_manager.get_handler_list()
        handler_incentives = db.get_all_handler_incentives()
        
        formatted = []
        for h in handlers:
            # Find matching incentive data
            total_incentive = 0
            for hi in handler_incentives:
                if hi[0] == h[0]:  # Match by ID
                    total_incentive = hi[2]
                    break
            
            formatted.append({
                'id': h[0],
                'name': h[1],
                'incentive_percentage': h[2],
                'incentive_type': h[3],
                'total_earned': total_incentive
            })
        
        return jsonify({
            'success': True,
            'data': formatted,
            'count': len(formatted)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/graphs/weekly')
def get_weekly_graph_data():
    """Get weekly sales vs expenses data"""
    try:
        today = datetime.now()
        dates = []
        sales_data = []
        expense_data = []
        
        for i in range(6, -1, -1):
            date = today - timedelta(days=i)
            date_str = date.strftime("%Y-%m-%d")
            dates.append(date.strftime("%m/%d"))
            
            summary = transaction_manager.get_summary(date_str, date_str)
            sales_data.append(summary['total_sales'])
            expense_data.append(summary['total_expenses'])
        
        return jsonify({
            'success': True,
            'data': {
                'labels': dates,
                'sales': sales_data,
                'expenses': expense_data
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/graphs/monthly')
def get_monthly_graph_data():
    """Get monthly trend data"""
    try:
        today = datetime.now()
        dates = []
        sales_data = []
        expense_data = []
        
        # Sample every 3 days for last 30 days
        for i in range(30, -1, -3):
            date = today - timedelta(days=i)
            date_str = date.strftime("%Y-%m-%d")
            dates.append(date.strftime("%m/%d"))
            
            summary = transaction_manager.get_summary(date_str, date_str)
            sales_data.append(summary['total_sales'])
            expense_data.append(summary['total_expenses'])
        
        return jsonify({
            'success': True,
            'data': {
                'labels': dates,
                'sales': sales_data,
                'expenses': expense_data
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/graphs/categories/<trans_type>')
def get_category_breakdown(trans_type):
    """Get category breakdown for sales or expenses"""
    try:
        today = datetime.now()
        start_date = f"{today.year}-{today.month:02d}-01"
        end_date = today.strftime("%Y-%m-%d")
        
        breakdown = transaction_manager.get_category_breakdown(trans_type, start_date, end_date)
        
        if not breakdown:
            return jsonify({
                'success': True,
                'data': {
                    'labels': [],
                    'values': []
                }
            })
        
        return jsonify({
            'success': True,
            'data': {
                'labels': list(breakdown.keys()),
                'values': list(breakdown.values())
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/graphs/profit')
def get_profit_data():
    """Get profit trend data"""
    try:
        today = datetime.now()
        dates = []
        profit_data = []
        
        # Sample every 3 days for last 30 days
        for i in range(30, -1, -3):
            date = today - timedelta(days=i)
            date_str = date.strftime("%Y-%m-%d")
            dates.append(date.strftime("%m/%d"))
            
            summary = transaction_manager.get_summary(date_str, date_str)
            profit_data.append(summary['profit'])
        
        return jsonify({
            'success': True,
            'data': {
                'labels': dates,
                'profit': profit_data
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


if __name__ == '__main__':
    print("\n" + "="*60)
    print("DigiCal Web Portal API Server")
    print("="*60)
    print(f"Server starting on http://{config.WEB_HOST}:{config.WEB_PORT}")
    print(f"Access from this device: http://localhost:{config.WEB_PORT}")
    if config.WEB_HOST == '0.0.0.0':
        print(f"Access from network: http://<your-ip>:{config.WEB_PORT}")
    print("="*60 + "\n")
    
    app.run(host=config.WEB_HOST, port=config.WEB_PORT, debug=False)

