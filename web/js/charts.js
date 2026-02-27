/**
 * DigiCal Web Portal - Chart Rendering
 * Uses Chart.js to create interactive visualizations
 */

// Chart instances (to prevent memory leaks)
const chartInstances = {};

// Chart.js default configuration
Chart.defaults.color = '#b8b8d1';
Chart.defaults.borderColor = '#2d3561';
Chart.defaults.font.family = "'Segoe UI', Tahoma, Geneva, Verdana, sans-serif";

// Destroy existing chart if it exists
function destroyChart(chartId) {
    if (chartInstances[chartId]) {
        chartInstances[chartId].destroy();
        delete chartInstances[chartId];
    }
}

// Weekly Bar Chart
function renderWeeklyChart(data, canvasId = 'weekly-chart') {
    destroyChart(canvasId);

    const ctx = document.getElementById(canvasId);
    if (!ctx) return;

    chartInstances[canvasId] = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: data.labels,
            datasets: [
                {
                    label: 'Sales',
                    data: data.sales,
                    backgroundColor: 'rgba(39, 174, 96, 0.7)',
                    borderColor: 'rgba(39, 174, 96, 1)',
                    borderWidth: 2,
                    borderRadius: 6
                },
                {
                    label: 'Expenses',
                    data: data.expenses,
                    backgroundColor: 'rgba(231, 76, 60, 0.7)',
                    borderColor: 'rgba(231, 76, 60, 1)',
                    borderWidth: 2,
                    borderRadius: 6
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: true,
                    position: 'top',
                    labels: {
                        padding: 15,
                        font: { size: 12 }
                    }
                },
                tooltip: {
                    backgroundColor: 'rgba(22, 33, 62, 0.95)',
                    padding: 12,
                    titleFont: { size: 14 },
                    bodyFont: { size: 13 },
                    callbacks: {
                        label: function (context) {
                            return `${context.dataset.label}: ₹${context.parsed.y.toFixed(2)}`;
                        }
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    grid: {
                        color: 'rgba(255, 255, 255, 0.05)'
                    },
                    ticks: {
                        callback: function (value) {
                            return '₹' + value;
                        }
                    }
                },
                x: {
                    grid: {
                        display: false
                    }
                }
            }
        }
    });
}

// Monthly Line Chart
function renderMonthlyChart(data) {
    destroyChart('monthly-chart');

    const ctx = document.getElementById('monthly-chart');
    if (!ctx) return;

    chartInstances['monthly-chart'] = new Chart(ctx, {
        type: 'line',
        data: {
            labels: data.labels,
            datasets: [
                {
                    label: 'Sales',
                    data: data.sales,
                    borderColor: 'rgba(39, 174, 96, 1)',
                    backgroundColor: 'rgba(39, 174, 96, 0.1)',
                    borderWidth: 3,
                    fill: true,
                    tension: 0.4,
                    pointRadius: 4,
                    pointHoverRadius: 6
                },
                {
                    label: 'Expenses',
                    data: data.expenses,
                    borderColor: 'rgba(231, 76, 60, 1)',
                    backgroundColor: 'rgba(231, 76, 60, 0.1)',
                    borderWidth: 3,
                    fill: true,
                    tension: 0.4,
                    pointRadius: 4,
                    pointHoverRadius: 6
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: true,
                    position: 'top',
                    labels: {
                        padding: 15,
                        font: { size: 12 }
                    }
                },
                tooltip: {
                    backgroundColor: 'rgba(22, 33, 62, 0.95)',
                    padding: 12,
                    titleFont: { size: 14 },
                    bodyFont: { size: 13 },
                    callbacks: {
                        label: function (context) {
                            return `${context.dataset.label}: ₹${context.parsed.y.toFixed(2)}`;
                        }
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    grid: {
                        color: 'rgba(255, 255, 255, 0.05)'
                    },
                    ticks: {
                        callback: function (value) {
                            return '₹' + value;
                        }
                    }
                },
                x: {
                    grid: {
                        display: false
                    }
                }
            }
        }
    });
}

// Pie Chart (for categories)
function renderPieChart(data, canvasId, title) {
    destroyChart(canvasId);

    const ctx = document.getElementById(canvasId);
    if (!ctx) return;

    // Check if there's data
    if (!data.labels || data.labels.length === 0) {
        // Show "No data" message
        ctx.getContext('2d').clearRect(0, 0, ctx.width, ctx.height);
        return;
    }

    const colors = [
        'rgba(52, 152, 219, 0.8)',
        'rgba(231, 76, 60, 0.8)',
        'rgba(39, 174, 96, 0.8)',
        'rgba(243, 156, 18, 0.8)',
        'rgba(155, 89, 182, 0.8)',
        'rgba(26, 188, 156, 0.8)',
        'rgba(230, 126, 34, 0.8)'
    ];

    chartInstances[canvasId] = new Chart(ctx, {
        type: 'pie',
        data: {
            labels: data.labels,
            datasets: [{
                data: data.values,
                backgroundColor: colors,
                borderColor: '#16213e',
                borderWidth: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: true,
                    position: 'right',
                    labels: {
                        padding: 15,
                        font: { size: 11 }
                    }
                },
                tooltip: {
                    backgroundColor: 'rgba(22, 33, 62, 0.95)',
                    padding: 12,
                    titleFont: { size: 14 },
                    bodyFont: { size: 13 },
                    callbacks: {
                        label: function (context) {
                            const total = context.dataset.data.reduce((a, b) => a + b, 0);
                            const percentage = ((context.parsed / total) * 100).toFixed(1);
                            return `${context.label}: ₹${context.parsed.toFixed(2)} (${percentage}%)`;
                        }
                    }
                }
            }
        }
    });
}

// Profit Trend Chart
function renderProfitChart(data) {
    destroyChart('profit-chart');

    const ctx = document.getElementById('profit-chart');
    if (!ctx) return;

    // Color bars based on positive/negative
    const backgroundColors = data.profit.map(value =>
        value >= 0 ? 'rgba(39, 174, 96, 0.7)' : 'rgba(231, 76, 60, 0.7)'
    );
    const borderColors = data.profit.map(value =>
        value >= 0 ? 'rgba(39, 174, 96, 1)' : 'rgba(231, 76, 60, 1)'
    );

    chartInstances['profit-chart'] = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: data.labels,
            datasets: [{
                label: 'Profit',
                data: data.profit,
                backgroundColor: backgroundColors,
                borderColor: borderColors,
                borderWidth: 2,
                borderRadius: 6
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    backgroundColor: 'rgba(22, 33, 62, 0.95)',
                    padding: 12,
                    titleFont: { size: 14 },
                    bodyFont: { size: 13 },
                    callbacks: {
                        label: function (context) {
                            const value = context.parsed.y;
                            return `Profit: ₹${value.toFixed(2)}`;
                        }
                    }
                }
            },
            scales: {
                y: {
                    grid: {
                        color: 'rgba(255, 255, 255, 0.05)'
                    },
                    ticks: {
                        callback: function (value) {
                            return '₹' + value;
                        }
                    }
                },
                x: {
                    grid: {
                        display: false
                    }
                }
            }
        }
    });
}

// Handler Performance Chart
function renderHandlerChart(handlers, canvasId = 'handlers-chart') {
    destroyChart(canvasId);

    const ctx = document.getElementById(canvasId);
    if (!ctx) return;

    if (!handlers || handlers.length === 0) {
        return;
    }

    const labels = handlers.map(h => h.name);
    const data = handlers.map(h => h.total_earned);

    // Gradient colors
    const colors = handlers.map((_, index) => {
        const hue = (index * 360 / handlers.length);
        return `hsla(${hue}, 70%, 60%, 0.8)`;
    });

    chartInstances[canvasId] = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Total Incentives',
                data: data,
                backgroundColor: colors,
                borderColor: colors.map(c => c.replace('0.8', '1')),
                borderWidth: 2,
                borderRadius: 6
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            indexAxis: 'y', // Horizontal bars
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    backgroundColor: 'rgba(22, 33, 62, 0.95)',
                    padding: 12,
                    titleFont: { size: 14 },
                    bodyFont: { size: 13 },
                    callbacks: {
                        label: function (context) {
                            return `Earned: ₹${context.parsed.x.toFixed(2)}`;
                        }
                    }
                }
            },
            scales: {
                x: {
                    beginAtZero: true,
                    grid: {
                        color: 'rgba(255, 255, 255, 0.05)'
                    },
                    ticks: {
                        callback: function (value) {
                            return '₹' + value;
                        }
                    }
                },
                y: {
                    grid: {
                        display: false
                    }
                }
            }
        }
    });
}
