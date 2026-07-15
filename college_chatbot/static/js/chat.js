/* CampusAI Chat Frontend Logic */

const state = {
  sessionId: null,
  sessionIds: JSON.parse(localStorage.getItem('campusai_sessions') || '[]'),
  provider: localStorage.getItem('campusai_provider') || 'groq',
  role: localStorage.getItem('campusai_role') || 'guest',
  isSending: false,
  recognition: null,
  isRecording: false,
};

const el = {
  chatScroll: document.getElementById('chatScroll'),
  welcomeScreen: document.getElementById('welcomeScreen'),
  messagesContainer: document.getElementById('messagesContainer'),
  typingIndicator: document.getElementById('typingIndicator'),
  suggestedQuestions: document.getElementById('suggestedQuestions'),
  messageInput: document.getElementById('messageInput'),
  sendBtn: document.getElementById('sendBtn'),
  micBtn: document.getElementById('micBtn'),
  providerSelect: document.getElementById('providerSelect'),
  roleSelect: document.getElementById('roleSelect'),
  newChatBtn: document.getElementById('newChatBtn'),
  conversationList: document.getElementById('conversationList'),
  sidebar: document.getElementById('sidebar'),
  sidebarOverlay: document.getElementById('sidebarOverlay'),
  openSidebarBtn: document.getElementById('openSidebarBtn'),
  closeSidebarBtn: document.getElementById('closeSidebarBtn'),
  themeToggleBtn: document.getElementById('themeToggleBtn'),
  searchHistoryInput: document.getElementById('searchHistoryInput'),
  exportTxtBtn: document.getElementById('exportTxtBtn'),
  exportPdfBtn: document.getElementById('exportPdfBtn'),
  quickActions: document.getElementById('quickActions'),
};

function uuid() {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
    const r = Math.random() * 16 | 0;
    const v = c === 'x' ? r : (r & 0x3 | 0x8);
    return v.toString(16);
  });
}

function saveSessionIds() {
  localStorage.setItem('campusai_sessions', JSON.stringify(state.sessionIds));
}

function initTheme() {
  const saved = localStorage.getItem('campusai_theme') || 'light';
  document.documentElement.setAttribute('data-bs-theme', saved);
  el.themeToggleBtn.innerHTML = saved === 'dark'
    ? '<i class="fa-solid fa-sun"></i>' : '<i class="fa-solid fa-moon"></i>';
}

el.themeToggleBtn.addEventListener('click', () => {
  const current = document.documentElement.getAttribute('data-bs-theme');
  const next = current === 'dark' ? 'light' : 'dark';
  document.documentElement.setAttribute('data-bs-theme', next);
  localStorage.setItem('campusai_theme', next);
  el.themeToggleBtn.innerHTML = next === 'dark'
    ? '<i class="fa-solid fa-sun"></i>' : '<i class="fa-solid fa-moon"></i>';
});

// Sidebar toggle (mobile)
el.openSidebarBtn?.addEventListener('click', () => {
  el.sidebar.classList.add('open');
  el.sidebarOverlay.classList.add('show');
});
el.closeSidebarBtn?.addEventListener('click', closeSidebar);
el.sidebarOverlay.addEventListener('click', closeSidebar);
function closeSidebar() {
  el.sidebar.classList.remove('open');
  el.sidebarOverlay.classList.remove('show');
}

// Provider / role persistence
el.providerSelect.value = state.provider;
el.roleSelect.value = state.role;
el.providerSelect.addEventListener('change', () => {
  state.provider = el.providerSelect.value;
  localStorage.setItem('campusai_provider', state.provider);
});
el.roleSelect.addEventListener('change', () => {
  state.role = el.roleSelect.value;
  localStorage.setItem('campusai_role', state.role);
  fetch('/auth/guest-session', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ role: state.role }),
  });
});

// Auto-resize textarea
el.messageInput.addEventListener('input', () => {
  el.messageInput.style.height = 'auto';
  el.messageInput.style.height = Math.min(el.messageInput.scrollHeight, 160) + 'px';
});

el.messageInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});

document.addEventListener('keydown', (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
    e.preventDefault();
    startNewChat();
  }
});

el.sendBtn.addEventListener('click', sendMessage);

el.newChatBtn.addEventListener('click', startNewChat);

el.quickActions?.addEventListener('click', (e) => {
  const btn = e.target.closest('.quick-action-btn');
  if (!btn) return;
  el.messageInput.value = btn.dataset.q;
  sendMessage();
});

function startNewChat() {
  state.sessionId = uuid();
  el.messagesContainer.innerHTML = '';
  el.welcomeScreen.classList.remove('d-none');
  el.suggestedQuestions.classList.add('d-none');
  el.suggestedQuestions.innerHTML = '';
  renderConversationList();
  closeSidebar();
}

function renderMarkdown(text) {
  const raw = marked.parse(text, { breaks: true });
  return DOMPurify.sanitize(raw);
}

function appendMessage(role, content, meta = {}) {
  el.welcomeScreen.classList.add('d-none');

  const row = document.createElement('div');
  row.className = `message-row ${role}`;

  const avatar = document.createElement('div');
  avatar.className = `avatar ${role}`;
  avatar.innerHTML = role === 'user'
    ? '<i class="fa-solid fa-user"></i>'
    : '<i class="fa-solid fa-graduation-cap"></i>';

  const bubbleWrap = document.createElement('div');

  const bubble = document.createElement('div');
  bubble.className = 'bubble';
  bubble.innerHTML = renderMarkdown(content);

  bubbleWrap.appendChild(bubble);

  if (role === 'assistant') {
    const metaRow = document.createElement('div');
    metaRow.className = 'message-meta';
    metaRow.innerHTML = `
      ${meta.provider ? `<span class="provider-tag">${meta.provider === 'claude' ? 'Claude' : 'ChatGPT'}</span>` : ''}
      ${meta.latency_ms ? `<span>${meta.latency_ms}ms</span>` : ''}
      <button class="copy-btn" title="Copy"><i class="fa-regular fa-copy"></i></button>
      <button class="regen-btn" title="Regenerate"><i class="fa-solid fa-rotate-right"></i></button>
      <button class="thumb-up-btn" title="Good response"><i class="fa-regular fa-thumbs-up"></i></button>
      <button class="thumb-down-btn" title="Poor response"><i class="fa-regular fa-thumbs-down"></i></button>
    `;
    bubbleWrap.appendChild(metaRow);

    if (meta.sources && meta.sources.length) {
      const srcDiv = document.createElement('div');
      srcDiv.className = 'sources-list';
      srcDiv.innerHTML = '<i class="fa-solid fa-book"></i> Sources: ' +
        meta.sources.map(s => s.source).filter((v, i, a) => a.indexOf(v) === i).join(', ');
      bubbleWrap.appendChild(srcDiv);
    }

    metaRow.querySelector('.copy-btn').addEventListener('click', () => {
      navigator.clipboard.writeText(content);
    });
    metaRow.querySelector('.regen-btn').addEventListener('click', () => regenerate());
    metaRow.querySelector('.thumb-up-btn').addEventListener('click', (e) => sendFeedback(meta.messageId, 'up', e.target));
    metaRow.querySelector('.thumb-down-btn').addEventListener('click', (e) => sendFeedback(meta.messageId, 'down', e.target));

    // Text-to-speech button
    const ttsBtn = document.createElement('button');
    ttsBtn.title = 'Read aloud';
    ttsBtn.innerHTML = '<i class="fa-solid fa-volume-high"></i>';
    ttsBtn.addEventListener('click', () => speakText(content));
    metaRow.appendChild(ttsBtn);
  }

  row.appendChild(avatar);
  row.appendChild(bubbleWrap);
  el.messagesContainer.appendChild(row);

  el.messagesContainer.querySelectorAll('pre code').forEach((block) => hljs.highlightElement(block));
  scrollToBottom();
}

function scrollToBottom() {
  el.chatScroll.scrollTop = el.chatScroll.scrollHeight;
}

function speakText(text) {
  if (!('speechSynthesis' in window)) return;
  window.speechSynthesis.cancel();
  const plain = text.replace(/[#*_`>-]/g, '');
  const utterance = new SpeechSynthesisUtterance(plain);
  window.speechSynthesis.speak(utterance);
}

async function sendFeedback(messageId, rating, targetEl) {
  if (!messageId) return;
  try {
    await fetch('/api/chat/feedback', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message_id: messageId, rating }),
    });
    targetEl.closest('button').style.color = rating === 'up' ? '#22c55e' : '#ef4444';
  } catch (err) { /* silent */ }
}

async function sendMessage() {
  const text = el.messageInput.value.trim();
  if (!text || state.isSending) return;

  if (!state.sessionId) {
    state.sessionId = uuid();
  }
  if (!state.sessionIds.includes(state.sessionId)) {
    state.sessionIds.push(state.sessionId);
    saveSessionIds();
  }

  appendMessage('user', text);
  el.messageInput.value = '';
  el.messageInput.style.height = 'auto';
  el.suggestedQuestions.classList.add('d-none');
  el.suggestedQuestions.innerHTML = '';

  state.isSending = true;
  el.sendBtn.disabled = true;
  el.typingIndicator.classList.remove('d-none');
  scrollToBottom();

  try {
    const res = await fetch('/api/chat/send', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: state.sessionId,
        provider: state.provider,
        message: text,
      }),
    });
    const data = await res.json();

    el.typingIndicator.classList.add('d-none');

    if (!data.success) {
      appendMessage('assistant', `⚠️ ${data.error || 'Something went wrong. Please try again.'}`);
      return;
    }

    appendMessage('assistant', data.message.content, {
      provider: data.message.ai_provider,
      latency_ms: data.message.latency_ms,
      sources: data.message.sources,
      messageId: data.message.id,
    });

    if (data.suggested_questions && data.suggested_questions.length) {
      renderSuggestedQuestions(data.suggested_questions);
    }

    renderConversationList();
  } catch (err) {
    el.typingIndicator.classList.add('d-none');
    appendMessage('assistant', '⚠️ Network error. Please check your connection and try again.');
  } finally {
    state.isSending = false;
    el.sendBtn.disabled = false;
  }
}

function renderSuggestedQuestions(questions) {
  el.suggestedQuestions.innerHTML = '';
  questions.forEach(q => {
    const chip = document.createElement('button');
    chip.className = 'suggested-question-chip';
    chip.textContent = q;
    chip.addEventListener('click', () => {
      el.messageInput.value = q;
      sendMessage();
    });
    el.suggestedQuestions.appendChild(chip);
  });
  el.suggestedQuestions.classList.remove('d-none');
}

async function regenerate() {
  if (!state.sessionId) return;
  el.typingIndicator.classList.remove('d-none');
  try {
    const res = await fetch('/api/chat/regenerate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: state.sessionId, provider: state.provider }),
    });
    const data = await res.json();
    el.typingIndicator.classList.add('d-none');
    if (data.success) {
      const lastBubble = el.messagesContainer.querySelector('.message-row.assistant:last-child .bubble');
      if (lastBubble) lastBubble.innerHTML = renderMarkdown(data.message.content);
    }
  } catch (err) {
    el.typingIndicator.classList.add('d-none');
  }
}

async function loadConversation(sessionId) {
  state.sessionId = sessionId;
  el.messagesContainer.innerHTML = '';
  const res = await fetch(`/api/chat/history/${sessionId}`);
  const data = await res.json();
  if (data.messages && data.messages.length) {
    el.welcomeScreen.classList.add('d-none');
    data.messages.forEach(m => {
      appendMessage(m.role, m.content, {
        provider: m.ai_provider, latency_ms: m.latency_ms, sources: m.sources, messageId: m.id,
      });
    });
  } else {
    el.welcomeScreen.classList.remove('d-none');
  }
  renderConversationList();
  closeSidebar();
}

async function renderConversationList() {
  const idsParam = state.sessionIds.join(',');
  if (!idsParam) {
    el.conversationList.innerHTML = '<div class="text-muted small px-3 py-2">No conversations yet</div>';
    return;
  }
  try {
    const res = await fetch(`/api/chat/conversations?session_ids=${encodeURIComponent(idsParam)}`);
    const data = await res.json();
    if (!data.conversations || !data.conversations.length) {
      el.conversationList.innerHTML = '<div class="text-muted small px-3 py-2">No conversations yet</div>';
      return;
    }
    el.conversationList.innerHTML = '';
    data.conversations.forEach(c => {
      const item = document.createElement('div');
      item.className = 'conversation-item' + (c.session_id === state.sessionId ? ' active' : '');
      item.innerHTML = `<span>${c.title}</span><i class="fa-solid fa-trash delete-convo-btn"></i>`;
      item.addEventListener('click', (e) => {
        if (e.target.closest('.delete-convo-btn')) return;
        loadConversation(c.session_id);
      });
      item.querySelector('.delete-convo-btn').addEventListener('click', async (e) => {
        e.stopPropagation();
        await fetch(`/api/chat/conversations/${c.session_id}`, { method: 'DELETE' });
        state.sessionIds = state.sessionIds.filter(id => id !== c.session_id);
        saveSessionIds();
        if (state.sessionId === c.session_id) startNewChat();
        renderConversationList();
      });
      el.conversationList.appendChild(item);
    });
  } catch (err) { /* silent */ }
}

// Searchable chat history
let searchTimeout;
el.searchHistoryInput.addEventListener('input', () => {
  clearTimeout(searchTimeout);
  searchTimeout = setTimeout(async () => {
    const q = el.searchHistoryInput.value.trim();
    if (!q) { renderConversationList(); return; }
    const res = await fetch(`/api/chat/search?q=${encodeURIComponent(q)}`);
    const data = await res.json();
    el.conversationList.innerHTML = '';
    if (!data.results.length) {
      el.conversationList.innerHTML = '<div class="text-muted small px-3 py-2">No matches found</div>';
      return;
    }
    data.results.forEach(r => {
      const item = document.createElement('div');
      item.className = 'conversation-item';
      item.innerHTML = `<span title="${r.message_snippet}">${r.conversation_title}</span>`;
      item.addEventListener('click', () => loadConversation(r.conversation_session_id));
      el.conversationList.appendChild(item);
    });
  }, 350);
});

// Export
el.exportTxtBtn.addEventListener('click', () => {
  if (!state.sessionId) return;
  window.open(`/api/chat/export/${state.sessionId}?format=txt`, '_blank');
});
el.exportPdfBtn.addEventListener('click', () => {
  if (!state.sessionId) return;
  window.open(`/api/chat/export/${state.sessionId}?format=pdf`, '_blank');
});

// Speech-to-text
function initSpeechRecognition() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) {
    el.micBtn.style.display = 'none';
    return;
  }
  state.recognition = new SpeechRecognition();
  state.recognition.continuous = false;
  state.recognition.interimResults = false;
  state.recognition.lang = 'en-US';

  state.recognition.onresult = (event) => {
    const transcript = event.results[0][0].transcript;
    el.messageInput.value += (el.messageInput.value ? ' ' : '') + transcript;
  };
  state.recognition.onend = () => {
    state.isRecording = false;
    el.micBtn.classList.remove('recording');
  };
  state.recognition.onerror = () => {
    state.isRecording = false;
    el.micBtn.classList.remove('recording');
  };
}

el.micBtn.addEventListener('click', () => {
  if (!state.recognition) return;
  if (state.isRecording) {
    state.recognition.stop();
  } else {
    state.recognition.start();
    state.isRecording = true;
    el.micBtn.classList.add('recording');
  }
});

// Init
initTheme();
initSpeechRecognition();
fetch('/auth/guest-session', {
  method: 'POST', headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ role: state.role }),
}).finally(() => {
  startNewChat();
});
