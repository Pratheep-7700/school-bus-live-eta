// Chart.js reports loader
function renderReportsCharts() {
    fetch('/api/reports/data')
        .then(res => res.json())
        .then(data => {
            // 1. Global MAE Chart
            new Chart(document.getElementById('chart-mae'), {
                type: 'bar',
                data: {
                    labels: ['Baseline System', 'Proposed System'],
                    datasets: [{
                        label: 'Mean Absolute Error (minutes)',
                        data: [data.mae_global.baseline, data.mae_global.proposed],
                        backgroundColor: ['#868e96', '#2b5c8f'],
                        borderWidth: 1,
                        borderRadius: 6
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { display: false } },
                    scales: { y: { beginAtZero: true, title: { display: true, text: 'MAE (minutes)' } } }
                }
            });

            // 2. Global RMSE Chart
            new Chart(document.getElementById('chart-rmse'), {
                type: 'bar',
                data: {
                    labels: ['Baseline System', 'Proposed System'],
                    datasets: [{
                        label: 'Root Mean Squared Error (minutes)',
                        data: [data.rmse_global.baseline, data.rmse_global.proposed],
                        backgroundColor: ['#868e96', '#2e7d32'],
                        borderWidth: 1,
                        borderRadius: 6
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { display: false } },
                    scales: { y: { beginAtZero: true, title: { display: true, text: 'RMSE (minutes)' } } }
                }
            });

            // 3. Enquiry Volume Chart
            new Chart(document.getElementById('chart-enquiries'), {
                type: 'bar',
                data: {
                    labels: ['Baseline System', 'Proposed System'],
                    datasets: [{
                        label: 'Customer Status Calls Count',
                        data: [data.enquiries.baseline, data.enquiries.proposed],
                        backgroundColor: ['#c62828', '#2b5c8f'],
                        borderWidth: 1,
                        borderRadius: 6
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { display: false } },
                    scales: { y: { beginAtZero: true, title: { display: true, text: 'Inquiry Calls Count' } } }
                }
            });

            // 4. Conditions breakdown (Error Analysis Chart)
            new Chart(document.getElementById('chart-conditions'), {
                type: 'bar',
                data: {
                    labels: data.error_analysis.categories,
                    datasets: [
                        {
                            label: 'Baseline MAE',
                            data: data.error_analysis.baseline,
                            backgroundColor: '#868e96',
                            borderRadius: 4
                        },
                        {
                            label: 'Proposed MAE',
                            data: data.error_analysis.proposed,
                            backgroundColor: '#2b5c8f',
                            borderRadius: 4
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { position: 'top' }
                    },
                    scales: {
                        y: { 
                            beginAtZero: true, 
                            title: { display: true, text: 'MAE (minutes)' } 
                        }
                    }
                }
            });

            // 5. Delay Reasons Distribution (Doughnut Chart)
            new Chart(document.getElementById('chart-delay-reasons'), {
                type: 'doughnut',
                data: {
                    labels: data.delay_reasons.labels,
                    datasets: [{
                        data: data.delay_reasons.counts,
                        backgroundColor: ['#ef6c00', '#2b5c8f', '#c62828', '#ffd54f'],
                        hoverOffset: 4
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { position: 'bottom' }
                    }
                }
            });
        })
        .catch(err => {
            console.error("Error loading reports charts data:", err);
        });
}

document.addEventListener('DOMContentLoaded', () => {
    renderReportsCharts();
});
