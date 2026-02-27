"""
Graph Generator for DigiCal
Creates visualizations for sales and expense data
"""
import matplotlib
matplotlib.use('TkAgg')  # Use TkAgg backend for Tkinter integration
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from datetime import datetime, timedelta
import config

class GraphGenerator:
    def __init__(self, transaction_manager):
        self.tm = transaction_manager
        try:
            plt.style.use('seaborn-v0_8-darkgrid')
        except OSError:
            try:
                plt.style.use('seaborn-darkgrid')
            except OSError:
                plt.style.use('ggplot')
    
    def _create_fig(self, figsize=None):
        """Internal helper to create a figure with optional custom size"""
        if figsize is None:
            figsize = config.GRAPH_FIGSIZE
        return Figure(figsize=figsize, dpi=config.GRAPH_DPI)

    def create_weekly_graph(self, figsize=None):
        """Create weekly sales vs expenses bar chart"""
        # Get data for the last 7 days
        today = datetime.now()
        dates = []
        sales_data = []
        expense_data = []
        
        for i in range(6, -1, -1):
            date = today - timedelta(days=i)
            date_str = date.strftime("%Y-%m-%d")
            dates.append(date.strftime("%m/%d"))
            
            summary = self.tm.get_summary(date_str, date_str)
            sales_data.append(summary['total_sales'])
            expense_data.append(summary['total_expenses'])
        
        # Create figure
        fig = self._create_fig(figsize)
        ax = fig.add_subplot(111)
        
        x = range(len(dates))
        width = 0.35
        
        ax.bar([i - width/2 for i in x], sales_data, width, label='Sales', color='#27AE60')
        ax.bar([i + width/2 for i in x], expense_data, width, label='Expenses', color='#E74C3C')
        
        ax.set_xlabel('Date')
        ax.set_ylabel('Amount (₹)')
        ax.set_title('Weekly Sales vs Expenses')
        ax.set_xticks(x)
        ax.set_xticklabels(dates, rotation=45)
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        fig.tight_layout()
        return fig
    
    def create_monthly_graph(self, figsize=None):
        """Create monthly sales vs expenses line graph"""
        # Get data for the last 30 days
        today = datetime.now()
        dates = []
        sales_data = []
        expense_data = []
        
        # Sample every 3 days to avoid cluttering
        for i in range(30, -1, -3):
            date = today - timedelta(days=i)
            date_str = date.strftime("%Y-%m-%d")
            dates.append(date.strftime("%m/%d"))
            
            summary = self.tm.get_summary(date_str, date_str)
            sales_data.append(summary['total_sales'])
            expense_data.append(summary['total_expenses'])
        
        # Create figure
        fig = self._create_fig(figsize)
        ax = fig.add_subplot(111)
        
        ax.plot(dates, sales_data, marker='o', label='Sales', color='#27AE60', linewidth=2)
        ax.plot(dates, expense_data, marker='s', label='Expenses', color='#E74C3C', linewidth=2)
        
        ax.set_xlabel('Date')
        ax.set_ylabel('Amount (₹)')
        ax.set_title('Monthly Sales vs Expenses Trend')
        ax.legend()
        ax.grid(True, alpha=0.3)
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)
        
        fig.tight_layout()
        return fig
    
    def create_category_pie_chart(self, trans_type='sales', period='month', figsize=None):
        """Create pie chart for category breakdown"""
        # Get date range based on period
        today = datetime.now()
        if period == 'week':
            start_date = (today - timedelta(days=7)).strftime("%Y-%m-%d")
            title_period = "Weekly"
        else:
            start_date = f"{today.year}-{today.month:02d}-01"
            title_period = "Monthly"
        
        end_date = today.strftime("%Y-%m-%d")
        
        # Get category breakdown
        breakdown = self.tm.get_category_breakdown(trans_type, start_date, end_date)
        
        if not breakdown:
            # Return empty figure if no data
            fig = self._create_fig(figsize)
            ax = fig.add_subplot(111)
            ax.text(0.5, 0.5, 'No data available', ha='center', va='center', fontsize=14)
            ax.axis('off')
            return fig
        
        # Create figure
        fig = self._create_fig(figsize)
        ax = fig.add_subplot(111)
        
        categories = list(breakdown.keys())
        amounts = list(breakdown.values())
        
        colors = ['#3498DB', '#E74C3C', '#27AE60', '#F39C12', '#9B59B6', '#1ABC9C', '#E67E22']
        
        ax.pie(amounts, labels=categories, autopct='%1.1f%%', startangle=90, colors=colors)
        ax.set_title(f'{title_period} {trans_type.capitalize()} by Category')
        
        fig.tight_layout()
        return fig
    
    def create_profit_trend_graph(self, figsize=None):
        """Create profit trend graph"""
        # Get data for the last 30 days
        today = datetime.now()
        dates = []
        profit_data = []
        
        # Sample every 3 days
        for i in range(30, -1, -3):
            date = today - timedelta(days=i)
            date_str = date.strftime("%Y-%m-%d")
            dates.append(date.strftime("%m/%d"))
            
            summary = self.tm.get_summary(date_str, date_str)
            profit_data.append(summary['profit'])
        
        # Create figure
        fig = self._create_fig(figsize)
        ax = fig.add_subplot(111)
        
        # Color positive profits green, negative red
        colors = ['#27AE60' if p >= 0 else '#E74C3C' for p in profit_data]
        
        ax.bar(dates, profit_data, color=colors, alpha=0.7)
        ax.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
        
        ax.set_xlabel('Date')
        ax.set_ylabel('Profit (₹)')
        ax.set_title('Daily Profit Trend (Last 30 Days)')
        ax.grid(True, alpha=0.3, axis='y')
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)
        
        fig.tight_layout()
        return fig
    
    def create_handler_performance_graph(self, handler_data, figsize=None):
        """Create handler incentive performance bar chart"""
        if not handler_data or len(handler_data) == 0:
            # Return empty figure if no data
            fig = self._create_fig(figsize)
            ax = fig.add_subplot(111)
            ax.text(0.5, 0.5, 'No handler data available', ha='center', va='center', fontsize=14)
            ax.axis('off')
            return fig
        
        # Extract data
        handler_names = [h[1] for h in handler_data]
        incentives = [h[2] for h in handler_data]
        
        # Create figure
        fig = self._create_fig(figsize)
        ax = fig.add_subplot(111)
        
        # Create bar chart
        colors = ['#27AE60' if i == 0 else '#3498DB' for i in range(len(handler_names))]
        bars = ax.bar(handler_names, incentives, color=colors, alpha=0.8)
        
        # Add value labels on top of bars
        for bar in bars:
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height,
                   f'₹{height:.2f}',
                   ha='center', va='bottom', fontsize=10)
        
        ax.set_xlabel('Handler Name')
        ax.set_ylabel('Total Incentives (₹)')
        ax.set_title('Handler Incentive Performance')
        ax.grid(True, alpha=0.3, axis='y')
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right')
        
        fig.tight_layout()
        return fig
