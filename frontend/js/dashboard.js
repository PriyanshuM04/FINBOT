const CATEGORY_EMOJIS = {
  food:'🍔', travel:'🚗', shopping:'🛍️',
  health:'💊', bills:'💡', entertainment:'🎬', other:'📦'
};

const token = window.location.pathname.split('/').pop();

async function loadData() {
  try {
    const res = await fetch(`/api/dashboard/${token}/summary`);
    if (!res.ok) {
      document.body.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:100vh;color:#6b6b85;font-family:monospace;">Dashboard not found.</div>';
      return;
    }
    const data = await res.json();
    render(data);
  } catch(e) {
    console.error(e);
  }
}

function render(data) {
  // Header
  document.getElementById('header-phone').textContent = `****${data.user_phone}`;
  document.getElementById('header-date').textContent = new Date().toLocaleDateString('en-IN', {
    day: 'numeric', month: 'short', year: 'numeric'
  });

  // Stats
  document.getElementById('stat-month').textContent = data.total_month.toLocaleString('en-IN');
  document.getElementById('stat-week').textContent = data.total_week.toLocaleString('en-IN');
  document.getElementById('stat-month-count').textContent = `${data.txn_count_month} transactions`;

  // Top category
  const cats = Object.entries(data.category_breakdown).sort((a,b) => b[1]-a[1]);
  if (cats.length > 0) {
    const [topCat, topAmt] = cats[0];
    document.getElementById('stat-top-cat').textContent =
      `${CATEGORY_EMOJIS[topCat] || '📦'} ${topCat.charAt(0).toUpperCase()+topCat.slice(1)}`;
    document.getElementById('stat-top-cat-amt').textContent =
      `₹${topAmt.toLocaleString('en-IN')} this month`;
  }

  // Charts
  renderPieChart(data.category_breakdown);
  renderBarChart(data.monthly_trend);

  // Top merchants
  const merchantsEl = document.getElementById('merchants-list');
  if (data.top_merchants.length === 0) {
    merchantsEl.innerHTML = '<div class="empty">No merchants yet</div>';
  } else {
    const maxAmt = data.top_merchants[0].amount;
    merchantsEl.innerHTML = data.top_merchants.map(m => `
      <div class="merchant-row">
        <div class="merchant-name">${m.name}</div>
        <div class="merchant-bar-wrap">
          <div class="merchant-bar" style="width:${(m.amount/maxAmt*100).toFixed(0)}%"></div>
        </div>
        <div class="merchant-amount">₹${m.amount.toLocaleString('en-IN')}</div>
      </div>
    `).join('');
  }

  // Recent transactions (last 5)
  const txnEl = document.getElementById('txn-list');
  if (data.recent_transactions.length === 0) {
    txnEl.innerHTML = '<div class="empty">No transactions yet. Forward a UPI screenshot to get started!</div>';
  } else {
    txnEl.innerHTML = data.recent_transactions.map(t => `
      <div class="txn-row">
        <div class="txn-icon">${CATEGORY_EMOJIS[t.category] || '📦'}</div>
        <div class="txn-info">
          <div class="txn-desc">${t.description}</div>
          <div class="txn-meta">${t.date} · ${t.source.replace('upi_','').toUpperCase()}</div>
        </div>
        <span class="cat-pill">${t.category}</span>
        <div class="txn-amount">₹${t.amount.toLocaleString('en-IN')}</div>
      </div>
    `).join('');
  }
}

loadData();