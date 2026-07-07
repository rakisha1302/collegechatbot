/* CampusAI Admin Dashboard Logic */

const tabs = document.querySelectorAll('.admin-tab');
const panels = document.querySelectorAll('.admin-panel');

tabs.forEach(tab => {
  tab.addEventListener('click', () => {
    tabs.forEach(t => t.classList.remove('active'));
    panels.forEach(p => p.classList.add('d-none'));
    tab.classList.add('active');
    document.getElementById(`tab-${tab.dataset.tab}`).classList.remove('d-none');

    if (tab.dataset.tab === 'documents') loadDocuments();
    if (tab.dataset.tab === 'chats') loadChatReview();
    if (tab.dataset.tab === 'traces') loadTraces();
    if (tab.dataset.tab === 'logs') loadLogs();
  });
});

let dailyChart, providerChart, feedbackChart;

async function loadOverview() {
  const res = await fetch('/admin/api/overview');
  const data = await res.json();
  if (!data.success) return;

  document.getElementById('statConversations').textContent = data.total_conversations;
  document.getElementById('statMessages').textContent = data.total_messages;
  document.getElementById('statDocuments').textContent = data.total_documents;
  document.getElementById('statLatency').textContent = data.avg_latency_ms ? `${data.avg_latency_ms}ms` : 'N/A';

  const dailyLabels = data.daily_message_counts.map(d => d.date);
  const dailyValues = data.daily_message_counts.map(d => d.count);
  if (dailyChart) dailyChart.destroy();
  dailyChart = new Chart(document.getElementById('dailyChart'), {
    type: 'line',
    data: { labels: dailyLabels, datasets: [{ label: 'Messages', data: dailyValues, borderColor: '#4f46e5', backgroundColor: 'rgba(79,70,229,0.1)', fill: true, tension: 0.3 }] },
    options: { plugins: { legend: { display: false } } },
  });

  const providerLabels = Object.keys(data.provider_usage);
  const providerValues = Object.values(data.provider_usage);
  if (providerChart) providerChart.destroy();
  providerChart = new Chart(document.getElementById('providerChart'), {
    type: 'doughnut',
    data: { labels: providerLabels.length ? providerLabels : ['No data'], datasets: [{ data: providerValues.length ? providerValues : [1], backgroundColor: ['#4f46e5', '#22c55e', '#e5e7eb'] }] },
  });

  if (feedbackChart) feedbackChart.destroy();
  feedbackChart = new Chart(document.getElementById('feedbackChart'), {
    type: 'bar',
    data: { labels: ['Positive', 'Negative'], datasets: [{ data: [data.feedback.up, data.feedback.down], backgroundColor: ['#22c55e', '#ef4444'] }] },
    options: { plugins: { legend: { display: false } } },
  });

  loadFaqKeywords();
}

async function loadFaqKeywords() {
  const res = await fetch('/admin/api/faq-analysis');
  const data = await res.json();
  const container = document.getElementById('faqKeywords');
  container.innerHTML = '';
  if (!data.success || !data.top_keywords.length) {
    container.innerHTML = '<span class="text-muted small">Not enough data yet.</span>';
    return;
  }
  data.top_keywords.forEach(k => {
    const chip = document.createElement('span');
    chip.className = 'keyword-chip';
    chip.textContent = `${k.term} (${k.count})`;
    container.appendChild(chip);
  });
}

async function loadDocuments() {
  const res = await fetch('/api/documents/');
  const data = await res.json();
  const tbody = document.getElementById('documentsTableBody');
  tbody.innerHTML = '';
  if (!data.success) return;
  data.documents.forEach(d => {
    const tr = document.createElement('tr');
    const statusBadge = d.status === 'indexed' ? 'success' : d.status === 'failed' ? 'danger' : 'secondary';
    tr.innerHTML = `
      <td>${d.original_filename}</td>
      <td><span class="badge text-bg-light">${d.category}</span></td>
      <td>${d.chunk_count}</td>
      <td><span class="badge text-bg-${statusBadge}">${d.status}</span></td>
      <td>${new Date(d.uploaded_at).toLocaleString()}</td>
      <td><button class="btn btn-sm btn-outline-danger delete-doc-btn" data-id="${d.id}"><i class="fa-solid fa-trash"></i></button></td>
    `;
    tbody.appendChild(tr);
  });
  tbody.querySelectorAll('.delete-doc-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
      await fetch(`/api/documents/${btn.dataset.id}`, { method: 'DELETE' });
      loadDocuments();
    });
  });
}

document.getElementById('uploadForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  const fileInput = document.getElementById('uploadFile');
  const category = document.getElementById('uploadCategory').value;
  const statusDiv = document.getElementById('uploadStatus');
  const btn = document.getElementById('uploadBtn');

  if (!fileInput.files.length) return;

  const formData = new FormData();
  formData.append('file', fileInput.files[0]);
  formData.append('category', category);

  btn.disabled = true;
  statusDiv.innerHTML = '<div class="text-muted small"><i class="fa-solid fa-spinner fa-spin"></i> Uploading and indexing document...</div>';

  try {
    const res = await fetch('/api/documents/upload', { method: 'POST', body: formData });
    const data = await res.json();
    if (data.success) {
      statusDiv.innerHTML = `<div class="text-success small"><i class="fa-solid fa-check"></i> Indexed ${data.document.chunk_count} chunks from "${data.document.original_filename}".</div>`;
      fileInput.value = '';
      loadDocuments();
    } else {
      statusDiv.innerHTML = `<div class="text-danger small"><i class="fa-solid fa-triangle-exclamation"></i> ${data.error || data.document?.error_message || 'Upload failed.'}</div>`;
    }
  } catch (err) {
    statusDiv.innerHTML = '<div class="text-danger small">Network error during upload.</div>';
  } finally {
    btn.disabled = false;
  }
});

async function loadChatReview() {
  const res = await fetch('/admin/api/chat-review');
  const data = await res.json();
  const tbody = document.getElementById('chatsTableBody');
  tbody.innerHTML = '';
  if (!data.success) return;
  data.conversations.forEach(c => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>${c.title}</td>
      <td>${c.ai_provider}</td>
      <td>${c.user_role}</td>
      <td>${c.message_count}</td>
      <td>${new Date(c.updated_at).toLocaleString()}</td>
    `;
    tbody.appendChild(tr);
  });
}

async function loadTraces() {
  const res = await fetch('/admin/api/langsmith-traces');
  const data = await res.json();
  const tbody = document.getElementById('tracesTableBody');
  const notice = document.getElementById('langsmithNotice');
  tbody.innerHTML = '';
  notice.classList.toggle('d-none', data.configured);
  if (!data.success) return;
  data.traces.forEach(t => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>${t.name}</td>
      <td>${t.status}</td>
      <td>${t.latency_ms ? Math.round(t.latency_ms) + 'ms' : '-'}</td>
      <td>${t.error || '-'}</td>
      <td>${t.start_time ? new Date(t.start_time).toLocaleString() : '-'}</td>
    `;
    tbody.appendChild(tr);
  });
}

async function loadLogs() {
  const res = await fetch('/admin/api/logs');
  const data = await res.json();
  const tbody = document.getElementById('logsTableBody');
  tbody.innerHTML = '';
  if (!data.success) return;
  data.logs.forEach(l => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>${l.event_type}</td>
      <td>${l.ai_provider || '-'}</td>
      <td>${l.success ? '<span class="text-success">✓</span>' : '<span class="text-danger">✗</span>'}</td>
      <td class="small">${l.details || '-'}</td>
      <td class="small">${new Date(l.created_at).toLocaleString()}</td>
    `;
    tbody.appendChild(tr);
  });
}

loadOverview();
