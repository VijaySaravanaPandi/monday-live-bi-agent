/**
 * Skylark Drones BI Command Center — Frontend v3
 * ────────────────────────────────────────────────
 * - ChatGPT-Style Left-Aligned Conversation Stream
 * - Real-Time KPI Dashboard Strip
 * - 5 Quick Prompts Bar positioned directly above the text box
 * - Terminator (Stop Generation) Button
 * - LocalStorage Multi-Thread Chat History in Sidebar
 * - Rich Markdown Table Parser for Sector/Stage/Revenue Breakdowns
 */

// ── Config ────────────────────────────────────────────────────────────────
const API_BASE = window.location.origin;
const STORAGE_KEY = 'skylark_bi_threads_v1';

// ── State ─────────────────────────────────────────────────────────────────
let threads = [];               // [{ id, title, createdAt, messages: [...] }]
let currentThreadId = null;     // Active thread ID
let conversationHistory = [];   // [{ role, content, data }]
let isLoading = false;
let abortController = null;

// ── DOM References ────────────────────────────────────────────────────────
const messagesArea     = document.getElementById('messages-area');
const userInput        = document.getElementById('user-input');
const actionBtn        = document.getElementById('action-btn');
const sendIcon         = actionBtn.querySelector('.send-icon');
const stopIcon         = actionBtn.querySelector('.stop-icon');
const statusChip       = document.getElementById('status-chip');
const statusDot        = statusChip.querySelector('.status-chip-dot');
const statusText       = statusChip.querySelector('.status-chip-text');
const menuToggle       = document.getElementById('menu-toggle');
const sidebar          = document.getElementById('sidebar');
const sidebarClose     = document.getElementById('sidebar-close');
const btnNewChat       = document.getElementById('btn-new-chat');
const btnClearAll      = document.getElementById('btn-clear-all');
const historyList      = document.getElementById('history-list');
const currentTitleEl   = document.getElementById('current-thread-title');

// ═══════════════════════════════════════════════════════════════════════════
// SIDEBAR & CHAT HISTORY (ChatGPT-Style)
// ═══════════════════════════════════════════════════════════════════════════

function loadThreadsFromStorage() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    threads = raw ? JSON.parse(raw) : [];
  } catch (e) {
    threads = [];
  }
}

function saveThreadsToStorage() {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(threads));
  } catch (e) {
    console.warn('Storage quota exceeded:', e);
  }
}

function renderHistoryList() {
  historyList.innerHTML = '';
  if (threads.length === 0) {
    historyList.innerHTML = `<div class="history-empty">No previous chats.<br>Start asking below!</div>`;
    return;
  }

  threads.slice().reverse().forEach(thread => {
    const item = document.createElement('button');
    item.className = `history-item${thread.id === currentThreadId ? ' active' : ''}`;
    item.setAttribute('data-id', thread.id);

    const titleSpan = document.createElement('span');
    titleSpan.className = 'history-title';
    titleSpan.textContent = thread.title || 'Untitled Query';

    const deleteBtn = document.createElement('span');
    deleteBtn.className = 'history-delete';
    deleteBtn.innerHTML = `&times;`;
    deleteBtn.title = 'Delete chat';
    deleteBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      deleteThread(thread.id);
    });

    item.appendChild(titleSpan);
    item.appendChild(deleteBtn);

    item.addEventListener('click', () => {
      selectThread(thread.id);
      if (window.innerWidth <= 768) closeSidebar();
    });

    historyList.appendChild(item);
  });
}

function createNewThread() {
  const newThread = {
    id: 'thread_' + Date.now(),
    title: 'New Conversation',
    createdAt: new Date().toISOString(),
    messages: [],
  };
  threads.push(newThread);
  currentThreadId = newThread.id;
  conversationHistory = [];
  saveThreadsToStorage();
  renderHistoryList();
  renderCurrentThreadMessages();
  currentTitleEl.textContent = 'Business Intelligence Command Center';
  userInput.focus();
}

function selectThread(threadId) {
  const thread = threads.find(t => t.id === threadId);
  if (!thread) return;

  currentThreadId = thread.id;
  conversationHistory = thread.messages.map(m => ({ role: m.role, content: m.content }));
  currentTitleEl.textContent = thread.title || 'Business Intelligence Command Center';

  renderHistoryList();
  renderCurrentThreadMessages();
}

function deleteThread(threadId) {
  threads = threads.filter(t => t.id !== threadId);
  saveThreadsToStorage();
  if (currentThreadId === threadId) {
    if (threads.length > 0) {
      selectThread(threads[threads.length - 1].id);
    } else {
      createNewThread();
    }
  } else {
    renderHistoryList();
  }
}

btnClearAll.addEventListener('click', () => {
  if (confirm('Clear all conversation history?')) {
    threads = [];
    saveThreadsToStorage();
    createNewThread();
  }
});

btnNewChat.addEventListener('click', () => {
  createNewThread();
  if (window.innerWidth <= 768) closeSidebar();
});

// Sidebar toggles
function openSidebar() {
  sidebar.classList.remove('hidden');
  if (window.innerWidth <= 768) {
    const overlay = document.createElement('div');
    overlay.className = 'sidebar-overlay';
    overlay.id = 'sidebar-overlay';
    overlay.addEventListener('click', closeSidebar);
    document.body.appendChild(overlay);
  }
}
function closeSidebar() {
  sidebar.classList.add('hidden');
  const overlay = document.getElementById('sidebar-overlay');
  if (overlay) overlay.remove();
}

menuToggle.addEventListener('click', () => {
  sidebar.classList.contains('hidden') ? openSidebar() : closeSidebar();
});
sidebarClose.addEventListener('click', closeSidebar);

if (window.innerWidth > 768) {
  sidebar.classList.remove('hidden');
} else {
  sidebar.classList.add('hidden');
}

// ═══════════════════════════════════════════════════════════════════════════
// QUICK PROMPT CHIPS (Above the input text box)
// ═══════════════════════════════════════════════════════════════════════════

document.querySelectorAll('.quick-chip').forEach(chip => {
  chip.addEventListener('click', () => {
    const q = chip.dataset.q;
    if (q) submitQuestion(q);
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// INPUT & TERMINATOR (STOP) BUTTON LOGIC
// ═══════════════════════════════════════════════════════════════════════════

userInput.addEventListener('input', () => {
  userInput.style.height = 'auto';
  userInput.style.height = Math.min(userInput.scrollHeight, 120) + 'px';
  if (!isLoading) {
    actionBtn.disabled = !userInput.value.trim();
  }
});

userInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    if (!actionBtn.disabled && !isLoading) {
      submitQuestion(userInput.value.trim());
    }
  }
});

// Action button handles both SEND and STOP (Terminator)
actionBtn.addEventListener('click', () => {
  if (isLoading) {
    // Stop / Terminate running request
    terminateCurrentRequest();
  } else {
    const q = userInput.value.trim();
    if (q) submitQuestion(q);
  }
});

function setButtonMode(mode) {
  if (mode === 'stop') {
    actionBtn.classList.add('is-stopping');
    actionBtn.disabled = false;
    actionBtn.title = 'Stop generation (Terminator)';
    sendIcon.style.display = 'none';
    stopIcon.style.display = 'block';
  } else {
    actionBtn.classList.remove('is-stopping');
    actionBtn.disabled = !userInput.value.trim();
    actionBtn.title = 'Send message';
    sendIcon.style.display = 'block';
    stopIcon.style.display = 'none';
  }
}

function terminateCurrentRequest() {
  if (abortController) {
    abortController.abort();
    abortController = null;
  }
  isLoading = false;
  setButtonMode('send');
  removeThinking();
  appendErrorMessage('Generation stopped by user.');
  setStatus('idle', 'Ready');
}

// ═══════════════════════════════════════════════════════════════════════════
// KPI DASHBOARD (Live Strip at the Top)
// ═══════════════════════════════════════════════════════════════════════════

async function loadMetrics() {
  try {
    const res = await fetch(`${API_BASE}/metrics`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    if (data.error) throw new Error(data.error);

    // Pipeline
    animateValue('kpi-pipeline', formatCurrency(data.pipeline_value));
    document.getElementById('kpi-pipeline-sub').textContent =
      `${data.deals_with_values || 0} of ${data.deal_count || 0} deals valued`;

    // Win Rate
    const winRateStr = (data.win_rate_pct !== null && data.win_rate_pct !== undefined)
      ? `${data.win_rate_pct}%`
      : 'N/A';
    animateValue('kpi-winrate', winRateStr);
    document.getElementById('kpi-winrate-sub').textContent =
      (data.total_closed_won || 0) + (data.total_closed_lost || 0) > 0
        ? `${data.total_closed_won || 0} won · ${data.total_closed_lost || 0} lost`
        : '0 resolved deals (active pipeline)';

    // Deals
    animateValue('kpi-deals', (data.deal_count || 0).toLocaleString());
    const stageCount = data.stage_breakdown ? Object.keys(data.stage_breakdown).length : 0;
    document.getElementById('kpi-deals-sub').textContent =
      `Across ${stageCount} pipeline stages`;

    // Revenue
    animateValue('kpi-revenue', formatCurrency(data.revenue_collected));
    document.getElementById('kpi-revenue-sub').textContent =
      `₹${formatShort(data.amount_receivable)} receivable`;

    // Mark cards loaded
    document.querySelectorAll('.kpi-card').forEach(c => c.classList.add('loaded'));

  } catch (err) {
    console.warn('Metrics load error:', err);
    document.querySelectorAll('.kpi-sub').forEach(el => {
      el.textContent = 'Live data available in chat';
      el.style.color = 'var(--text-muted)';
    });
    document.querySelectorAll('.kpi-card').forEach(c => c.classList.add('loaded'));
  }
}

// Make top KPI cards interactive
document.getElementById('kpi-card-pipeline')?.addEventListener('click', () => {
  submitQuestion("What's the total pipeline value?");
});
document.getElementById('kpi-card-winrate')?.addEventListener('click', () => {
  submitQuestion("What's our win rate?");
});
document.getElementById('kpi-card-deals')?.addEventListener('click', () => {
  submitQuestion("Show me deal count by stage.");
});
document.getElementById('kpi-card-revenue')?.addEventListener('click', () => {
  submitQuestion("Show me revenue collected, billed, and receivable from work orders.");
});

function formatCurrency(value) {
  if (!value || value === 0) return '₹0';
  if (value >= 1e9)  return '₹' + (value / 1e9).toFixed(2) + 'B';
  if (value >= 1e7)  return '₹' + (value / 1e7).toFixed(1) + 'Cr';
  if (value >= 1e5)  return '₹' + (value / 1e5).toFixed(1) + 'L';
  if (value >= 1e3)  return '₹' + (value / 1e3).toFixed(1) + 'K';
  return '₹' + value.toLocaleString();
}

function formatShort(value) {
  if (!value || value === 0) return '0';
  if (value >= 1e9)  return (value / 1e9).toFixed(1) + 'B';
  if (value >= 1e7)  return (value / 1e7).toFixed(1) + 'Cr';
  if (value >= 1e5)  return (value / 1e5).toFixed(1) + 'L';
  if (value >= 1e3)  return (value / 1e3).toFixed(0) + 'K';
  return value.toLocaleString();
}

function animateValue(elementId, finalText) {
  const el = document.getElementById(elementId);
  if (!el) return;
  el.style.opacity = '0';
  el.style.transform = 'translateY(6px)';
  setTimeout(() => {
    el.textContent = finalText;
    el.style.transition = 'opacity 0.4s ease, transform 0.4s ease';
    el.style.opacity = '1';
    el.style.transform = 'translateY(0)';
  }, 80);
}

// ═══════════════════════════════════════════════════════════════════════════
// CORE CHAT FLOW
// ═══════════════════════════════════════════════════════════════════════════

async function submitQuestion(question) {
  if (isLoading || !question) return;

  // Make sure we have an active thread
  let activeThread = threads.find(t => t.id === currentThreadId);
  if (!activeThread) {
    activeThread = {
      id: 'thread_' + Date.now(),
      title: question.slice(0, 32) + (question.length > 32 ? '…' : ''),
      createdAt: new Date().toISOString(),
      messages: [],
    };
    threads.push(activeThread);
    currentThreadId = activeThread.id;
  } else if (activeThread.messages.length === 0) {
    activeThread.title = question.slice(0, 32) + (question.length > 32 ? '…' : '');
    currentTitleEl.textContent = activeThread.title;
  }

  // Remove welcome state if present
  const ws = document.getElementById('welcome-state');
  if (ws) ws.remove();

  // Add User Message
  appendUserMessage(question);
  activeThread.messages.push({ role: 'user', content: question, time: new Date().toISOString() });
  conversationHistory.push({ role: 'user', content: question });
  saveThreadsToStorage();
  renderHistoryList();

  // Clear input
  userInput.value = '';
  userInput.style.height = 'auto';

  // Setup Terminator (Stop) Button & AbortController
  isLoading = true;
  setButtonMode('stop');
  setStatus('loading', 'Querying Monday.com…');
  appendThinking();

  abortController = new AbortController();

  try {
    const response = await fetch(`${API_BASE}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      signal: abortController.signal,
      body: JSON.stringify({
        question,
        history: conversationHistory.slice(-12),
      }),
    });

    removeThinking();

    if (!response.ok) {
      const err = await response.json().catch(() => ({ detail: 'Unknown error' }));
      throw new Error(err.detail || `HTTP ${response.status}`);
    }

    const data = await response.json();
    appendAgentMessage(data);

    activeThread.messages.push({
      role: 'assistant',
      content: data.answer,
      data_quality_notes: data.data_quality_notes,
      partial_failure: data.partial_failure,
      partial_failure_reason: data.partial_failure_reason,
      clarification_needed: data.clarification_needed,
      time: new Date().toISOString(),
    });
    conversationHistory.push({ role: 'assistant', content: data.answer });
    saveThreadsToStorage();

    setStatus('ok', 'Ready');

  } catch (err) {
    removeThinking();
    if (err.name !== 'AbortError') {
      appendErrorMessage(err.message || 'Something went wrong. Please try again.');
      setStatus('error', 'Error');
      setTimeout(() => setStatus('idle', 'Ready'), 4000);
    }
  } finally {
    isLoading = false;
    abortController = null;
    setButtonMode('send');
    scrollToBottom();
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// MESSAGE RENDERING (ChatGPT-Style: All Left-Aligned)
// ═══════════════════════════════════════════════════════════════════════════

function renderCurrentThreadMessages() {
  messagesArea.innerHTML = '';
  const activeThread = threads.find(t => t.id === currentThreadId);

  if (!activeThread || activeThread.messages.length === 0) {
    messagesArea.innerHTML = buildWelcomeHTML();
    return;
  }

  activeThread.messages.forEach(msg => {
    if (msg.role === 'user') {
      appendUserMessage(msg.content, false);
    } else {
      appendAgentMessage(msg, false);
    }
  });
  scrollToBottom();
}

function appendUserMessage(text, scroll = true) {
  const el = document.createElement('div');
  el.className = 'message user';

  el.innerHTML = `
    <div class="msg-avatar" aria-hidden="true">U</div>
    <div class="msg-body">
      <div class="msg-sender">You <span class="msg-sender-sub">${formatTime(new Date())}</span></div>
      <div class="msg-bubble">${escapeHtml(text)}</div>
    </div>
  `;
  messagesArea.appendChild(el);
  if (scroll) scrollToBottom();
}

function appendAgentMessage(data, scroll = true) {
  const isClarification = data.clarification_needed;
  const wrapper = document.createElement('div');
  wrapper.className = `message agent${isClarification ? ' clarification' : ''}`;

  const notes = data.data_quality_notes || [];
  let caveatsHTML = '';
  if (notes.length > 0) {
    const listItems = notes.map(n => `<li>${escapeHtml(n)}</li>`).join('');
    caveatsHTML = `
      <button class="caveats-toggle" aria-expanded="false" onclick="toggleCaveats(this)">
        ⚠ Data caveats (${notes.length}) <span class="caret" aria-hidden="true">▾</span>
      </button>
      <div class="caveats-body">
        <ul>${listItems}</ul>
      </div>
    `;
  }

  let partialHTML = '';
  if (data.partial_failure && data.partial_failure_reason) {
    partialHTML = `
      <div class="caveats-toggle" style="background: var(--red-soft); border-color: rgba(239,68,68,0.25); color: var(--red);">
        ⚠ Partial data: ${escapeHtml(data.partial_failure_reason)}
      </div>
    `;
  }

  wrapper.innerHTML = `
    <div class="msg-avatar" aria-hidden="true">✦</div>
    <div class="msg-body">
      <div class="msg-sender">Skylark BI Agent <span class="msg-sender-sub">${formatTime(new Date())}</span></div>
      <div class="msg-bubble">${formatMarkdown(data.content || data.answer || '')}</div>
      ${caveatsHTML}
      ${partialHTML}
    </div>
  `;

  messagesArea.appendChild(wrapper);
  if (scroll) scrollToBottom();
}

function appendErrorMessage(errorText) {
  const wrapper = document.createElement('div');
  wrapper.className = 'message agent';
  wrapper.innerHTML = `
    <div class="msg-avatar" aria-hidden="true">⚠</div>
    <div class="msg-body">
      <div class="msg-sender">System Alert</div>
      <div class="msg-bubble" style="border-color: rgba(239,68,68,0.3); background: var(--red-soft); color: #fca5a5;">
        ${escapeHtml(errorText)}
      </div>
    </div>
  `;
  messagesArea.appendChild(wrapper);
  scrollToBottom();
}

function appendThinking() {
  const wrapper = document.createElement('div');
  wrapper.className = 'message agent thinking-msg';
  wrapper.id = 'thinking-msg';
  wrapper.innerHTML = `
    <div class="msg-avatar" aria-hidden="true">✦</div>
    <div class="msg-body">
      <div class="thinking-indicator">
        <div class="thinking-dots" aria-hidden="true">
          <div class="thinking-dot"></div>
          <div class="thinking-dot"></div>
          <div class="thinking-dot"></div>
        </div>
        <span>Querying Monday.com & analyzing metrics…</span>
      </div>
    </div>
  `;
  messagesArea.appendChild(wrapper);
  scrollToBottom();
}

function removeThinking() {
  const el = document.getElementById('thinking-msg');
  if (el) el.remove();
}

window.toggleCaveats = function(btn) {
  const body = btn.nextElementSibling;
  if (body) {
    const isOpen = body.classList.toggle('open');
    btn.classList.toggle('open', isOpen);
    btn.setAttribute('aria-expanded', String(isOpen));
  }
};

// ═══════════════════════════════════════════════════════════════════════════
// MARKDOWN TABLE & TEXT PARSER
// ═══════════════════════════════════════════════════════════════════════════

function formatMarkdown(rawText) {
  if (!rawText) return '';

  // 1. Process Markdown Tables first
  let text = renderMarkdownTables(rawText);

  // 2. Escape other HTML characters (outside table tags)
  // Bold, italic, code
  text = text
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.*?)\*/g, '<em>$1</em>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/^[•\-\*] (.+)$/gm, '<li>$1</li>')
    .replace(/(<li>.*<\/li>\n?)+/g, m => `<ul>${m}</ul>`)
    .replace(/^#{3,4} (.+)$/gm, '<h4>$1</h4>')
    .replace(/\n\n+/g, '</p><p>')
    .replace(/\n/g, '<br>')
    .replace(/^(?!<[uolhtdp])(.+)/, '<p>$1</p>');

  return text;
}

/**
 * Converts Markdown table syntax (| Header 1 | Header 2 |\n|---|---|...)
 * into responsive styled HTML tables.
 */
function renderMarkdownTables(text) {
  const lines = text.split('\n');
  const result = [];
  let inTable = false;
  let tableRows = [];

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim();

    if (line.startsWith('|') && line.endsWith('|')) {
      inTable = true;
      tableRows.push(line);
    } else {
      if (inTable) {
        result.push(convertTableRowsToHTML(tableRows));
        inTable = false;
        tableRows = [];
      }
      result.push(escapeHtml(lines[i]));
    }
  }

  if (inTable && tableRows.length > 0) {
    result.push(convertTableRowsToHTML(tableRows));
  }

  return result.join('\n');
}

function convertTableRowsToHTML(rows) {
  if (rows.length < 2) return rows.join('\n');

  // Filter out delimiter line (|---|---|)
  const headerLine = rows[0];
  const dataLines = rows.slice(1).filter(r => !/^[\|\s\-:]+$/.test(r));

  const parseCells = (row) =>
    row.slice(1, -1).split('|').map(c => escapeHtml(c.trim()));

  const headers = parseCells(headerLine);
  let html = `<div class="table-wrapper"><table class="data-table"><thead><tr>`;
  headers.forEach(h => { html += `<th>${h}</th>`; });
  html += `</tr></thead><tbody>`;

  dataLines.forEach(row => {
    const cells = parseCells(row);
    html += `<tr>`;
    cells.forEach((cell, idx) => {
      html += `<td>${cell || '—'}</td>`;
    });
    html += `</tr>`;
  });

  html += `</tbody></table></div>`;
  return html;
}

// ═══════════════════════════════════════════════════════════════════════════
// UI HELPERS
// ═══════════════════════════════════════════════════════════════════════════

function setStatus(state, text) {
  statusChip.className = `status-chip ${state}`;
  statusText.textContent = text;
}

function scrollToBottom() {
  messagesArea.scrollTo({ top: messagesArea.scrollHeight, behavior: 'smooth' });
}

function formatTime(date) {
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function buildWelcomeHTML() {
  return `
    <div class="welcome-state" id="welcome-state">
      <div class="welcome-badge">EXECUTIVE INTELLIGENCE ASSISTANT</div>
      <div class="welcome-icon-wrap">
        <div class="welcome-icon-ring ring-1"></div>
        <div class="welcome-icon-ring ring-2"></div>
        <div class="welcome-icon-core">
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
            <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/>
          </svg>
        </div>
      </div>
      <h2 class="welcome-title">Ask anything about Skylark Drones</h2>
      <p class="welcome-sub">Ask any business intelligence question — queries are computed dynamically against Monday.com with 100% verified math.</p>
    </div>
  `;
}

// ═══════════════════════════════════════════════════════════════════════════
// INITIALIZATION
// ═══════════════════════════════════════════════════════════════════════════

loadThreadsFromStorage();

if (threads.length === 0) {
  createNewThread();
} else {
  selectThread(threads[threads.length - 1].id);
}

loadMetrics();
userInput.focus();
