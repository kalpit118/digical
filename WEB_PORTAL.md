# DigiCal Web Portal - User Guide

## 🚀 Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements-web.txt
```

### 2. Start the Server
```bash
python api.py
```

Or use the launcher:
```bash
python run_web.py
```

### 3. Access the Portal
Open your browser and go to:
- **Local access**: http://localhost:8080
- **Network access**: http://YOUR_IP_ADDRESS:8080 (after configuring for network access)

## 📊 Features

### Dashboard
- Real-time business metrics (sales, expenses, profit)
- Summary cards for today, this week, and this month
- Recent transactions list
- Quick overview charts

### Transactions
- Complete transaction history
- Filter by type (sales/expenses)
- View payment methods and handlers
- Detailed transaction information

### Handlers
- Handler performance metrics
- Total incentives earned
- Visual comparison chart
- Individual handler statistics

### Analytics
- Weekly sales vs expenses chart
- Monthly trend analysis
- Category breakdown pie charts
- Profit trend visualization
- Handler performance comparison

## 🔧 Configuration

Edit `config.py` to customize:

```python
# Web Portal settings
WEB_HOST = '127.0.0.1'  # Change to '0.0.0.0' for network access
WEB_PORT = 8080  # Change if port is in use
API_REFRESH_INTERVAL = 30  # Auto-refresh interval in seconds
```

## 🌐 Network Access

To access the portal from other devices on your network:

1. **Update config.py**:
   ```python
   WEB_HOST = '0.0.0.0'
   ```

2. **Find your IP address**:
   ```bash
   ipconfig
   ```
   Look for "IPv4 Address" under your active network adapter

3. **Configure Windows Firewall**:
   - Open Windows Defender Firewall
   - Click "Advanced settings"
   - Click "Inbound Rules" → "New Rule"
   - Select "Port" → Next
   - Select "TCP" and enter port `8080` → Next
   - Select "Allow the connection" → Next
   - Check all profiles → Next
   - Name it "DigiCal Web Portal" → Finish

4. **Access from other devices**:
   ```
   http://YOUR_IP_ADDRESS:8080
   ```

## 🐛 Troubleshooting

### Port Permission Error
**Error**: "An attempt was made to access a socket in a way forbidden by its access permissions"

**Solutions**:
1. **Run as Administrator**: Right-click Command Prompt → "Run as administrator"
2. **Try a different port**: Edit `WEB_PORT` in `config.py` (try 8000, 8888, 9000)
3. **Check if port is in use**:
   ```bash
   netstat -ano | findstr :8080
   ```
4. **Disable Hyper-V** (if installed):
   ```bash
   net stop winnat
   ```

### Server Won't Start
1. Ensure dependencies are installed: `pip install -r requirements-web.txt`
2. Check Python version (requires Python 3.7+)
3. Verify database file exists: `digical.db`

### Data Not Loading
1. Check if the desktop GUI has created transactions
2. Verify database connection in `database.py`
3. Check browser console for JavaScript errors (F12)

### Charts Not Displaying
1. Ensure internet connection (Chart.js loads from CDN)
2. Check browser compatibility (use Chrome, Firefox, or Edge)
3. Clear browser cache and reload

## 📱 Mobile Access

The portal is fully responsive and works on:
- Desktop browsers (Chrome, Firefox, Edge, Safari)
- Tablets (iPad, Android tablets)
- Mobile phones (iOS, Android)

Simply access the portal URL from your mobile browser when connected to the same network.

## 🔄 Auto-Refresh

The portal automatically refreshes data every 30 seconds. You can:
- Change the interval in `config.py` (`API_REFRESH_INTERVAL`)
- Manually refresh by switching tabs or reloading the page

## 💡 Tips

1. **Keep the server running**: The web portal only works while `api.py` is running
2. **Use multiple devices**: Access from desktop, tablet, and phone simultaneously
3. **Bookmark the URL**: Save http://localhost:8080 for quick access
4. **Check handler**: The current active handler is shown in the header
5. **View different time periods**: Use the Analytics tab for historical trends

## 🔐 Security Note

Currently, the portal has no authentication. It's designed for local network use only. Do not expose it to the public internet without adding proper authentication.

## 📞 Support

If you encounter issues:
1. Check the terminal/command prompt for error messages
2. Review this troubleshooting guide
3. Verify all dependencies are installed
4. Try running as Administrator

## 🎨 Browser Compatibility

Tested and working on:
- ✅ Google Chrome 90+
- ✅ Mozilla Firefox 88+
- ✅ Microsoft Edge 90+
- ✅ Safari 14+
- ✅ Mobile browsers (Chrome Mobile, Safari iOS)

## 📊 API Endpoints

For developers, the following API endpoints are available:

- `GET /api/summary` - Business summary (daily/weekly/monthly)
- `GET /api/transactions` - Transaction history
- `GET /api/calculations` - Calculation history
- `GET /api/handlers` - Handler performance data
- `GET /api/graphs/weekly` - Weekly chart data
- `GET /api/graphs/monthly` - Monthly trend data
- `GET /api/graphs/categories/sales` - Sales category breakdown
- `GET /api/graphs/categories/expense` - Expense category breakdown
- `GET /api/graphs/profit` - Profit trend data

Visit http://localhost:8080/api for the full API documentation.
