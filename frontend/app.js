/**
 * Skylark Drones BI Command Center — Frontend v2
 * ────────────────────────────────────────────────
 * Dashboard KPI cards, conversational AI chat, and sidebar navigation.
 */

// ── Config ────────────────────────────────────────────────────────────────
const API_BASE = window.location.origin;

// ── State ─────────────────────────────────────────────────────────────────
let conversationHistory = [];
let isLoading = false;
let metricsLoaded = false;

// ── DOM Refs ──────────────────────────────────────────────────────────────
const messagesArea  = document.getElementById('messages-area');
const userInput     = document.getElementById('user-input');
const sendBtn       = document.getElementById('send-btn');
const welcomeState  = document.getElementById('welcome-state');
const statusChip    = document.getElementById('status-chip');
const statusDot     = statusChip.querySelector('.status-chip-dot');
const statusText    = statusChip.querySelector('.status-chip-text');
const menuToggle    = document.getElementById('menu-toggle');
const sidebar       = document.getElementById('sidebar');
const sidebarClose  = document.getElementById('sidebar-close');
const btnClear      = document.getElementById('btn-clear');

// ── Sidebar Toggle ────────────────────────────────────────────────────────
function openSidebar() {
  sidebar.classList.remove('hidden');
  // Add overlay on mobile
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

// On desktop, sidebar starts visible
if (window.innerWidth > 768) {
  sidebar.classList.remove('hidden');
} else {
  sidebar.classList.add('hidden');
}

// ── Quick Query Buttons ───────────────────────────────────────────────────
const QUICK_QUERIES = {
  'q-pipeline':   "What's the total pipeline value?",
  'q-winrate':    "What's our win rate?",
  'q-stages':     "Show me deal count by stage.",
  'q-mining':     "How is the Mining sector performing across sales and operations?",
  'q-revenue':    "Show me revenue collected, billed, and receivable from work orders.",
  'q-leadership': "Give me a leadership update for the board.",
};

Object.entries(QUICK_QUERIES).forEach(([id, question]) => {
  const btn = document.getElementById(id);
  if (btn) {
    btn.addEventListener('click', () => {
      if (window.innerWidth <= 768) closeSidebar();
      submitQuestion(question);
    });
  }
});

// ── Example Chips ─────────────────────────────────────────────────────────
document.querySelectorAll('.chip').forEach(chip => {
  chip.addEventListener('click', () => {
    const q = chip.dataset.q;
    if (q) submitQuestion(q);
  });
});

// ── Clear Conversation ────────────────────────────────────────────────────
btnClear.addEventListener('click', () => {
  conversationHistory = [];
  messagesArea.innerHTML = '';
  // Rebuild welcome state
  messagesArea.innerHTML = buildWelcomeHTML();
  rebindChips();
  setStatus('idle', 'Ready');
});

// ── Input Handling ────────────────────────────────────────────────────────
userInput.addEventListener('input', () => {
  userInput.style.height = 'auto';
  userInput.style.height = Math.min(userInput.scrollHeight, 120) + 'px';
  sendBtn.disabled = !userInput.value.trim() || isLoading;
});

userInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    if (!sendBtn.disabled) submitQuestion(userInput.value.trim());
  }
});

sendBtn.addEventListener('click', () => {
  const q = userInput.value.trim();
  if (q) submitQuestion(q);
});

// ═══════════════════════════════════════════════════════════════════════════
// KPI DASHBOARD — Fetches live metrics on page load
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

    // Mark cards as loaded (removes shimmer)
    document.querySelectorAll('.kpi-card').forEach(c => c.classList.add('loaded'));
    metricsLoaded = true;

  } catch (err) {
    console.warn('Metrics load failed:', err);
    document.querySelectorAll('.kpi-sub').forEach(el => {
      el.textContent = 'Live data available in chat';
      el.style.color = 'var(--text-muted)';
    });
    document.querySelectorAll('.kpi-card').forEach(c => c.classList.add('loaded'));
  }
}

// Make KPI cards interactive
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
  el.style.opacity = '0';
  el.style.transform = 'translateY(8px)';
  setTimeout(() => {
    el.textContent = finalText;
    el.style.transition = 'opacity 0.5s ease, transform 0.5s ease';
    el.style.opacity = '1';
    el.style.transform = 'translateY(0)';
  }, 100);
}

// ═══════════════════════════════════════════════════════════════════════════
// CHAT LOGIC
// ═══════════════════════════════════════════════════════════════════════════

async function submitQuestion(question) {
  if (isLoading || !question) return;

  // Remove welcome state
  const ws = document.getElementById('welcome-state');
  if (ws) ws.remove();

  appendUserMessage(question);
  conversationHistory.push({ role: 'user', content: question });

  userInput.value = '';
  userInput.style.height = 'auto';
  sendBtn.disabled = true;

  const thinkingEl = appendThinking();
  setStatus('loading', 'Analyzing…');
  isLoading = true;

  try {
    const response = await fetch(`${API_BASE}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        question,
        history: conversationHistory.slice(-12),
      }),
    });

    thinkingEl.remove();

    if (!response.ok) {
      const err = await response.json().catch(() => ({ detail: 'Unknown error' }));
      throw new Error(err.detail || `HTTP ${response.status}`);
    }

    const data = await response.json();
    appendAgentMessage(data);
    conversationHistory.push({ role: 'assistant', content: data.answer });
    setStatus('ok', 'Ready');

  } catch (err) {
    thinkingEl.remove();
    appendErrorMessage(err.message || 'Something went wrong. Please try again.');
    setStatus('error', 'Error');
    setTimeout(() => setStatus('idle', 'Ready'), 4000);
  } finally {
    isLoading = false;
    sendBtn.disabled = !userInput.value.trim();
    scrollToBottom();
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// MESSAGE RENDERING
// ═══════════════════════════════════════════════════════════════════════════

function appendUserMessage(text) {
  const el = createMessageEl('user', escapeHtml(text));
  messagesArea.appendChild(el);
  scrollToBottom();
}

function appendAgentMessage(data) {
  const isClarification = data.clarification_needed;
  const wrapper = document.createElement('div');
  wrapper.className = `message agent${isClarification ? ' clarification' : ''}`;

  const avatar = document.createElement('div');
  avatar.className = 'msg-avatar';
  avatar.setAttribute('aria-hidden', 'true');
  avatar.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/></svg>`;

  const body = document.createElement('div');
  body.className = 'msg-body';

  const bubble = document.createElement('div');
  bubble.className = 'msg-bubble';
  bubble.innerHTML = formatMarkdown(data.answer);

  const time = document.createElement('span');
  time.className = 'msg-time';
  time.textContent = formatTime(new Date());

  body.appendChild(bubble);
  body.appendChild(time);

  // Data quality caveats
  if (data.data_quality_notes && data.data_quality_notes.length > 0) {
    body.appendChild(buildCaveatsEl(data.data_quality_notes));
  }

  // Partial failure warning
  if (data.partial_failure && data.partial_failure_reason) {
    const warn = document.createElement('div');
    warn.className = 'caveats-toggle';
    warn.style.background = 'var(--red-soft)';
    warn.style.borderColor = 'rgba(239,68,68,0.2)';
    warn.style.color = 'var(--red)';
    warn.innerHTML = `⚠ Partial data: ${escapeHtml(data.partial_failure_reason)}`;
    body.appendChild(warn);
  }

  wrapper.appendChild(avatar);
  wrapper.appendChild(body);
  messagesArea.appendChild(wrapper);
  scrollToBottom();
}

function appendErrorMessage(errorText) {
  const wrapper = document.createElement('div');
  wrapper.className = 'message agent';

  const avatar = document.createElement('div');
  avatar.className = 'msg-avatar';
  avatar.setAttribute('aria-hidden', 'true');
  avatar.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>`;

  const body = document.createElement('div');
  body.className = 'msg-body';

  const bubble = document.createElement('div');
  bubble.className = 'msg-bubble';
  bubble.style.borderColor = 'rgba(239,68,68,0.25)';
  bubble.style.background = 'var(--red-soft)';
  bubble.innerHTML = `⚠ ${escapeHtml(errorText)}`;

  body.appendChild(bubble);
  wrapper.appendChild(avatar);
  wrapper.appendChild(body);
  messagesArea.appendChild(wrapper);
  scrollToBottom();
}

function appendThinking() {
  const wrapper = document.createElement('div');
  wrapper.className = 'message agent';

  const avatar = document.createElement('div');
  avatar.className = 'msg-avatar';
  avatar.setAttribute('aria-hidden', 'true');
  avatar.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/></svg>`;

  const body = document.createElement('div');
  body.className = 'msg-body';

  const indicator = document.createElement('div');
  indicator.className = 'thinking-indicator';
  indicator.innerHTML = `
    <div class="thinking-dots" aria-hidden="true">
      <div class="thinking-dot"></div>
      <div class="thinking-dot"></div>
      <div class="thinking-dot"></div>
    </div>
    <span>Querying Monday.com…</span>
  `;

  body.appendChild(indicator);
  wrapper.appendChild(avatar);
  wrapper.appendChild(body);
  messagesArea.appendChild(wrapper);
  scrollToBottom();
  return wrapper;
}

function createMessageEl(role, htmlContent) {
  const wrapper = document.createElement('div');
  wrapper.className = `message ${role}`;

  const avatar = document.createElement('div');
  avatar.className = 'msg-avatar';
  avatar.setAttribute('aria-hidden', 'true');
  avatar.textContent = role === 'user' ? 'U' : '✦';

  const body = document.createElement('div');
  body.className = 'msg-body';

  const bubble = document.createElement('div');
  bubble.className = 'msg-bubble';
  bubble.innerHTML = htmlContent;

  const time = document.createElement('span');
  time.className = 'msg-time';
  time.textContent = formatTime(new Date());

  body.appendChild(bubble);
  body.appendChild(time);
  wrapper.appendChild(avatar);
  wrapper.appendChild(body);
  return wrapper;
}

function buildCaveatsEl(notes) {
  const container = document.createElement('div');

  const toggle = document.createElement('button');
  toggle.className = 'caveats-toggle';
  toggle.setAttribute('aria-expanded', 'false');
  toggle.innerHTML = `⚠ Data caveats (${notes.length}) <span class="caret" aria-hidden="true">▾</span>`;

  const body = document.createElement('div');
  body.className = 'caveats-body';
  const ul = document.createElement('ul');
  notes.forEach(n => {
    const li = document.createElement('li');
    li.textContent = n;
    ul.appendChild(li);
  });
  body.appendChild(ul);

  toggle.addEventListener('click', () => {
    const isOpen = body.classList.toggle('open');
    toggle.classList.toggle('open', isOpen);
    toggle.setAttribute('aria-expanded', String(isOpen));
  });

  container.appendChild(toggle);
  container.appendChild(body);
  return container;
}

// ═══════════════════════════════════════════════════════════════════════════
// HELPERS
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

function formatMarkdown(text) {
  return escapeHtml(text)
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.*?)\*/g, '<em>$1</em>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/^[•\-\*] (.+)$/gm, '<li>$1</li>')
    .replace(/(<li>.*<\/li>\n?)+/g, m => `<ul>${m}</ul>`)
    .replace(/^#{3,4} (.+)$/gm, '<h4>$1</h4>')
    .replace(/\n\n+/g, '</p><p>')
    .replace(/\n/g, '<br>')
    .replace(/^(?!<[uolh])(.+)/, '<p>$1</p>');
}

function buildWelcomeHTML() {
  return `
    <div class="welcome-state" id="welcome-state">
      <div class="welcome-badge">AI-POWERED BUSINESS INTELLIGENCE</div>
      <div class="welcome-icon-wrap">
        <div class="welcome-icon-ring ring-1"></div>
        <div class="welcome-icon-ring ring-2"></div>
        <div class="welcome-icon-core">
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
            <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/>
          </svg>
        </div>
      </div>
      <h2 class="welcome-title">What would you like to know?</h2>
      <p class="welcome-sub">Ask any business question — I'll query Monday.com in real-time and give you a data-driven answer with full transparency.</p>
      <div class="welcome-chips">
        <button class="chip" data-q="What's the total pipeline value?">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2v20M17 5H9.5a3.5 3.5 0 000 7h5a3.5 3.5 0 010 7H6"/></svg>
          Pipeline value
        </button>
        <button class="chip" data-q="What's our win rate?">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/></svg>
          Win rate
        </button>
        <button class="chip" data-q="How is Mining performing across sales and operations?">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M2 22L12 2l10 20H2z"/></svg>
          Mining overview
        </button>
        <button class="chip" data-q="Give me a leadership update for the board.">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
          Leadership briefing
        </button>
      </div>
    </div>
  `;
}

function rebindChips() {
  document.querySelectorAll('.chip').forEach(chip => {
    chip.addEventListener('click', () => {
      const q = chip.dataset.q;
      if (q) submitQuestion(q);
    });
  });
}

// ═══════════════════════════════════════════════════════════════════════════
// INIT
// ═══════════════════════════════════════════════════════════════════════════
userInput.focus();
loadMetrics();  // Populate KPI cards on page load
