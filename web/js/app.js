/**
 * DigiCal Web Portal - Main Application Logic
 * Handles data fetching, UI updates, and user interactions
 */

// Configuration
const API_BASE_URL = window.location.origin;
const REFRESH_INTERVAL = 30000; // 30 seconds

// Global state
let refreshTimer = null;
let currentTab = 'dashboard';

// Initialize app when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    console.log('DigiCal Web Portal initialized');
    initializeApp();
});

function initializeApp() {
    setupNavigation();
    loadAllData();
    startAutoRefresh();
}

// Navigation
function setupNavigation() {
    const navTabs = document.querySelectorAll('.nav-tab');
    navTabs.forEach(tab => {
        tab.addEventListener('click', () => {
            const tabName = tab.dataset.tab;
            switchTab(tabName);
        });
    });

    // Transaction filter
    const transFilter = document.getElementById('trans-type-filter');
    if (transFilter) {
        transFilter.addEventListener('change', () => {
            loadTransactions(transFilter.value);
        });
    }
}

function switchTab(tabName) {
    currentTab = tabName;

    // Update nav tabs
    document.querySelectorAll('.nav-tab').forEach(tab => {
        tab.classList.remove('active');
        if (tab.dataset.tab === tabName) {
            tab.classList.add('active');
        }
    });

    // Update content
    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.remove('active');
    });
    document.getElementById(`${tabName}-tab`).classList.add('active');

    // Load tab-specific data
    loadTabData(tabName);
}

function loadTabData(tabName) {
    switch (tabName) {
        case 'dashboard':
            loadDashboardData();
            break;
        case 'transactions':
            loadTransactions();
            break;
        case 'handlers':
            loadHandlers();
            break;
        case 'analytics':
            loadAnalytics();
            break;
    }
}

// Data Loading Functions
async function loadAllData() {
    try {
        updateStatus('online');
        await loadSummary();
        await loadRecentTransactions();
        await loadDashboardCharts();
    } catch (error) {
        console.error('Error loading data:', error);
        updateStatus('offline');
    }
}

async function loadDashboardData() {
    await loadSummary();
    await loadRecentTransactions();
    await loadDashboardCharts();
}

async function loadSummary() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/summary`);
        const data = await response.json();

        if (data.success) {
            const { daily, weekly, monthly, current_handler, timestamp } = data.data;

            // Update summary cards
            updateElement('today-sales', formatCurrency(daily.total_sales));
            updateElement('week-sales', `Week: ${formatCurrency(weekly.total_sales)}`);
            updateElement('month-sales', `Month: ${formatCurrency(monthly.total_sales)}`);

            updateElement('today-expenses', formatCurrency(daily.total_expenses));
            updateElement('week-expenses', `Week: ${formatCurrency(weekly.total_expenses)}`);
            updateElement('month-expenses', `Month: ${formatCurrency(monthly.total_expenses)}`);

            updateElement('today-profit', formatCurrency(daily.profit));
            updateElement('week-profit', `Week: ${formatCurrency(weekly.profit)}`);
            updateElement('month-profit', `Month: ${formatCurrency(monthly.profit)}`);

            // Update header info
            updateElement('current-handler', current_handler ? current_handler.name : 'None');
            updateElement('last-updated', formatTime(timestamp));
        }
    } catch (error) {
        console.error('Error loading summary:', error);
    }
}

async function loadRecentTransactions() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/transactions?limit=10`);
        const data = await response.json();

        if (data.success) {
            const tbody = document.getElementById('recent-transactions');
            tbody.innerHTML = '';

            if (data.data.length === 0) {
                tbody.innerHTML = '<tr><td colspan="6" class="loading">No transactions yet</td></tr>';
                return;
            }

            data.data.forEach(trans => {
                const row = document.createElement('tr');
                row.innerHTML = `
                    <td>${formatDate(trans.date)}</td>
                    <td><span class="badge ${trans.type}">${trans.type}</span></td>
                    <td>${trans.category}</td>
                    <td class="amount ${trans.type === 'sales' ? 'positive' : 'negative'}">
                        ${formatCurrency(trans.amount)}
                    </td>
                    <td>${trans.payment_method || 'Cash'}</td>
                    <td>${trans.handler_name || '-'}</td>
                `;
                tbody.appendChild(row);
            });
        }
    } catch (error) {
        console.error('Error loading recent transactions:', error);
    }
}

async function loadTransactions(type = '') {
    try {
        const url = type ? `${API_BASE_URL}/api/transactions?type=${type}` : `${API_BASE_URL}/api/transactions`;
        const response = await fetch(url);
        const data = await response.json();

        if (data.success) {
            const tbody = document.getElementById('all-transactions');
            tbody.innerHTML = '';

            if (data.data.length === 0) {
                tbody.innerHTML = '<tr><td colspan="7" class="loading">No transactions found</td></tr>';
                return;
            }

            data.data.forEach(trans => {
                const row = document.createElement('tr');
                row.innerHTML = `
                    <td>${formatDateTime(trans.created_at)}</td>
                    <td><span class="badge ${trans.type}">${trans.type}</span></td>
                    <td>${trans.category}</td>
                    <td>${trans.description || '-'}</td>
                    <td class="amount ${trans.type === 'sales' ? 'positive' : 'negative'}">
                        ${formatCurrency(trans.amount)}
                    </td>
                    <td>${trans.payment_method || 'Cash'}</td>
                    <td>${trans.handler_name || '-'}</td>
                `;
                tbody.appendChild(row);
            });
        }
    } catch (error) {
        console.error('Error loading transactions:', error);
    }
}

async function loadHandlers() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/handlers`);
        const data = await response.json();

        if (data.success) {
            const tbody = document.getElementById('handlers-table');
            tbody.innerHTML = '';

            if (data.data.length === 0) {
                tbody.innerHTML = '<tr><td colspan="4" class="loading">No handlers yet</td></tr>';
                return;
            }

            data.data.forEach(handler => {
                const row = document.createElement('tr');
                const incentiveDisplay = handler.incentive_type === 'percentage'
                    ? `${handler.incentive_percentage}%`
                    : `₹${handler.incentive_percentage}`;

                row.innerHTML = `
                    <td><strong>${handler.name}</strong></td>
                    <td>${incentiveDisplay}</td>
                    <td><span class="badge ${handler.incentive_type === 'percentage' ? 'sales' : 'expense'}">${handler.incentive_type}</span></td>
                    <td class="amount positive">${formatCurrency(handler.total_earned)}</td>
                `;
                tbody.appendChild(row);
            });

            // Update handler chart
            renderHandlerChart(data.data);
        }
    } catch (error) {
        console.error('Error loading handlers:', error);
    }
}

async function loadDashboardCharts() {
    try {
        // Load weekly chart for dashboard
        const weeklyResponse = await fetch(`${API_BASE_URL}/api/graphs/weekly`);
        const weeklyData = await weeklyResponse.json();
        if (weeklyData.success) {
            renderWeeklyChart(weeklyData.data, 'dashboard-weekly-chart');
        }

        // Load handler chart for dashboard
        const handlersResponse = await fetch(`${API_BASE_URL}/api/handlers`);
        const handlersData = await handlersResponse.json();
        if (handlersData.success) {
            renderHandlerChart(handlersData.data, 'dashboard-handler-chart');
        }
    } catch (error) {
        console.error('Error loading dashboard charts:', error);
    }
}

async function loadAnalytics() {
    try {
        // Weekly chart
        const weeklyResponse = await fetch(`${API_BASE_URL}/api/graphs/weekly`);
        const weeklyData = await weeklyResponse.json();
        if (weeklyData.success) {
            renderWeeklyChart(weeklyData.data, 'weekly-chart');
        }

        // Monthly chart
        const monthlyResponse = await fetch(`${API_BASE_URL}/api/graphs/monthly`);
        const monthlyData = await monthlyResponse.json();
        if (monthlyData.success) {
            renderMonthlyChart(monthlyData.data);
        }

        // Sales pie chart
        const salesResponse = await fetch(`${API_BASE_URL}/api/graphs/categories/sales`);
        const salesData = await salesResponse.json();
        if (salesData.success) {
            renderPieChart(salesData.data, 'sales-pie-chart', 'Sales');
        }

        // Expense pie chart
        const expenseResponse = await fetch(`${API_BASE_URL}/api/graphs/categories/expense`);
        const expenseData = await expenseResponse.json();
        if (expenseData.success) {
            renderPieChart(expenseData.data, 'expense-pie-chart', 'Expense');
        }

        // Profit chart
        const profitResponse = await fetch(`${API_BASE_URL}/api/graphs/profit`);
        const profitData = await profitResponse.json();
        if (profitData.success) {
            renderProfitChart(profitData.data);
        }
    } catch (error) {
        console.error('Error loading analytics:', error);
    }
}

// Utility Functions
function updateElement(id, value) {
    const element = document.getElementById(id);
    if (element) {
        element.textContent = value;
    }
}

function updateStatus(status) {
    const indicator = document.getElementById('status-indicator');
    if (indicator) {
        if (status === 'online') {
            indicator.classList.remove('offline');
            indicator.querySelector('span:last-child').textContent = 'Live';
        } else {
            indicator.classList.add('offline');
            indicator.querySelector('span:last-child').textContent = 'Offline';
        }
    }
}

function formatCurrency(amount) {
    return `₹${parseFloat(amount).toFixed(2)}`;
}

function formatDate(dateStr) {
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-IN', { month: 'short', day: 'numeric' });
}

function formatDateTime(dateStr) {
    const date = new Date(dateStr);
    return date.toLocaleString('en-IN', {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}

function formatTime(dateStr) {
    const date = new Date(dateStr);
    return date.toLocaleTimeString('en-IN', {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
    });
}

// Auto-refresh
function startAutoRefresh() {
    if (refreshTimer) {
        clearInterval(refreshTimer);
    }

    refreshTimer = setInterval(() => {
        console.log('Auto-refreshing data...');
        loadTabData(currentTab);
    }, REFRESH_INTERVAL);
}

// Make switchTab globally available
window.switchTab = switchTab;
