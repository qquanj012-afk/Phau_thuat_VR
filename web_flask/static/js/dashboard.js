/* DASHBOARD CHARTS */
document.addEventListener('DOMContentLoaded', function() {
  const init = window.DASHBOARD_INIT;
  if (!init) return;

  const mainCtx = document.getElementById('mainChart').getContext('2d');
  let mainChart = new Chart(mainCtx, {
    type: 'line',
    data: {
      labels: init.labels,
      datasets: [
        { label: 'Raw', data: init.raw, borderColor: '#4d9fff', backgroundColor: 'rgba(77,159,255,0.06)', tension: 0.4, fill: true, borderWidth: 2, pointRadius: 2 },
        { label: 'Processed', data: init.processed, borderColor: '#00d4aa', backgroundColor: 'rgba(0,212,170,0.06)', tension: 0.4, fill: true, borderWidth: 2, pointRadius: 2 },
        { label: '3D Mesh', data: init.mesh, borderColor: '#ffb347', backgroundColor: 'rgba(255,179,71,0.06)', tension: 0.4, fill: true, borderWidth: 2, pointRadius: 2 }
      ]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { grid: { color: 'rgba(42,48,69,0.5)' }, ticks: { color: '#5a6280', font: { family: 'IBM Plex Mono', size: 11 } } },
        y: {
          beginAtZero: true,
          grace: '5%',
          ticks: {
            // Tự động giới hạn số lượng ticks (tối đa 8)
            maxTicksLimit: 8,
            // Định dạng số lớn thành 1k, 1M...
            callback: function(value) {
              if (value >= 1000000) return (value / 1000000).toFixed(1) + 'M';
              if (value >= 1000) return (value / 1000).toFixed(1) + 'k';
              return value;
            },
            color: '#5a6280',
            font: { family: 'IBM Plex Mono', size: 11 }
          },
          grid: { color: 'rgba(42,48,69,0.5)' }
        }
      }
    }
  });

  const pieCtx = document.getElementById('pieChart').getContext('2d');
  let pieChart = new Chart(pieCtx, {
    type: 'doughnut',
    data: {
      labels: ['Raw', 'Processed', '3D Mesh'],
      datasets: [{
        data: [init.stats.raw, init.stats.processed, init.stats.mesh],
        backgroundColor: ['#4d9fff', '#00d4aa', '#ffb347'],
        borderColor: '#11141c',
        borderWidth: 3,
        hoverOffset: 4
      }]
    },
    options: {
      responsive: true, maintainAspectRatio: false, cutout: '72%',
      plugins: { legend: { display: false } }
    }
  });

  function updateStatsAndLegend(raw, processed, mesh) {
    document.getElementById('stat-raw').textContent = raw;
    document.getElementById('stat-proc').textContent = processed;
    document.getElementById('stat-mesh').textContent = mesh;
    const total = raw + processed + mesh;
    const legendContainer = document.getElementById('pie-legend-container');
    legendContainer.innerHTML = `
      <div class="legend-item"><div class="legend-dot" style="background:#4d9fff"></div>Raw ${raw} (${total ? (raw/total*100).toFixed(1) : 0}%)</div>
      <div class="legend-item"><div class="legend-dot" style="background:#00d4aa"></div>Processed ${processed} (${total ? (processed/total*100).toFixed(1) : 0}%)</div>
      <div class="legend-item"><div class="legend-dot" style="background:#ffb347"></div>Meshes ${mesh} (${total ? (mesh/total*100).toFixed(1) : 0}%)</div>
    `;
  }

  function fetchDataAndUpdate(start, end) {
    fetch(`/api/stats/timeseries?start=${start}&end=${end}`)
      .then(res => res.json())
      .then(data => {
        if (data.error) {
          showToast(data.error, true);
          return;
        }
        mainChart.data.labels = data.labels.map(d => d.substring(5));
        mainChart.data.datasets[0].data = data.raw;
        mainChart.data.datasets[1].data = data.processed;
        mainChart.data.datasets[2].data = data.mesh;
        mainChart.update();

        pieChart.data.datasets[0].data = [data.total_raw, data.total_processed, data.total_mesh];
        pieChart.update();

        updateStatsAndLegend(data.total_raw, data.total_processed, data.total_mesh);
      })
      .catch(() => showToast('Lỗi tải dữ liệu', true));
  }

  const startInput = document.getElementById('startDate');
  const endInput = document.getElementById('endDate');

  document.getElementById('applyDateBtn').addEventListener('click', () => {
    const start = startInput.value;
    const end = endInput.value;
    if (!start || !end) {
      showToast('Vui lòng chọn đầy đủ ngày', true);
      return;
    }
    if (end < start) {
      showToast('Ngày kết thúc phải sau hoặc bằng ngày bắt đầu', true);
      return;
    }
    fetchDataAndUpdate(start, end);
  });

  document.getElementById('resetDateBtn').addEventListener('click', () => {
    const today = new Date();
    const end = today.toISOString().split('T')[0];
    const start = new Date(today);
    start.setDate(today.getDate() - 7);
    const startStr = start.toISOString().split('T')[0];
    startInput.value = startStr;
    endInput.value = end;
    fetchDataAndUpdate(startStr, end);
  });

  // 🔄 Tự động tải dữ liệu thực khi trang load
  fetchDataAndUpdate(init.defaultStart, init.defaultEnd);
});