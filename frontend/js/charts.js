const PLOTLY_COLORS = [
  '#7c5cfc','#fc5c7d','#2ecc71','#f39c12','#3498db','#e74c3c','#9b59b6'
];

function renderPieChart(categoryBreakdown) {
  const cats = Object.entries(categoryBreakdown).sort((a,b) => b[1]-a[1]);
  if (cats.length === 0) {
    document.getElementById('chart-pie').innerHTML = '<div class="empty">No data yet</div>';
    return;
  }
  const labels = cats.map(([k]) => k.charAt(0).toUpperCase() + k.slice(1));
  const values = cats.map(([,v]) => v);

  Plotly.newPlot('chart-pie', [{
    type: 'pie',
    labels, values,
    hole: 0.55,
    marker: { colors: PLOTLY_COLORS },
    textinfo: 'label+percent',
    textfont: { family: 'DM Mono', size: 11, color: '#e8e8f0' },
    hovertemplate: '<b>%{label}</b><br>₹%{value}<br>%{percent}<extra></extra>',
  }], {
    paper_bgcolor: 'transparent',
    plot_bgcolor: 'transparent',
    showlegend: false,
    margin: { t:10, b:10, l:10, r:10 },
  }, { responsive: true, displayModeBar: false });
}

function renderBarChart(monthlyTrend) {
  const now = new Date();
  const last3 = [];
  for (let i = 2; i >= 0; i--) {
    const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
    last3.push(d.toLocaleDateString('en-IN', { month: 'short', year: 'numeric' }));
  }
  const barAmounts = last3.map(m => monthlyTrend[m] || 0);

  Plotly.newPlot('chart-bar', [{
    type: 'bar',
    x: last3,
    y: barAmounts,
    marker: {
      color: barAmounts.map((_,i) => i === 2 ? '#7c5cfc' : '#2a2a38'),
      line: { width: 0 },
    },
    hovertemplate: '<b>%{x}</b><br>₹%{y}<extra></extra>',
  }], {
    paper_bgcolor: 'transparent',
    plot_bgcolor: 'transparent',
    font: { family: 'DM Mono', color: '#6b6b85', size: 11 },
    xaxis: { gridcolor: '#2a2a38', zeroline: false },
    yaxis: { gridcolor: '#2a2a38', zeroline: false, tickprefix: '₹' },
    margin: { t:10, b:40, l:60, r:10 },
    bargap: 0.4,
  }, { responsive: true, displayModeBar: false });
}