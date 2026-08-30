/**
 * Skylark Drones BI Agent — Frontend Chat Logic
 * -----------------------------------------------
 * Manages conversation state, API calls, message rendering,
 * and UI interactions.
 *
 * Config: change API_BASE_URL to point at your deployed instance.
 */

// ── Config ──────────────────────────────────────────────────────────────────
const API_BASE_URL = window.location.origin; // auto-resolves for local + Render

// ── State ────────────────────────────────────────────────────────────────────
let conversationHistory = [];   // [{role, content}, ...]
let isLoading = false;

// ── DOM refs ─────────────────────────────────────────────────────────────────
const messagesArea   = document.getElementById('messages-area');
const userInput      = document.getElementById('user-input');
const sendBtn        = document.getElementById('send-btn');
const welcomeState   = document.getElementById('welcome-state');
const headerStatus   = document.getElementById('header-status');
const statusDot      = headerStatus.querySelector('.status-dot');
const statusText     = headerStatus.querySelector('.status-text');
const sidebarToggle  = document.getElementById('sidebar-toggle');
const sidebar        = document.querySelector('.sidebar');
const btnClear       = document.getElementById('btn-clear');

// ── Sidebar toggle ────────────────────────────────────────────────────────────
sidebarToggle.addEventListener('click', () => {
  sidebar.classList.toggle('collapsed');
});

// ── Quick query buttons ───────────────────────────────────────────────────────
const QUICK_QUESTIONS = {
  'q-pipeline':   "What's the total pipeline value?",
  'q-winrate':    "What's our win rate?",
  'q-mining':     "How is the Mining sector performing overall?",
  'q-leadership': "Give me a leadership update for the board.",
  'q-revenue':    "Show me revenue collected so far from work orders.",
};

Object.entries(QUICK_QUESTIONS).forEach(([id, question]) => {
  const btn = document.getElementById(id);
  if (btn) {
    btn.addEventListener('click', () => submitQuestion(question));
  }
});

// ── Example chips (welcome state) ────────────────────────────────────────────
document.querySelectorAll('.example-chip').forEach(chip => {
  chip.addEventListener('click', () => {
    const q = chip.dataset.q;
    if (q) submitQuestion(q);
  });
});

// ── Clear conversation ────────────────────────────────────────────────────────
btnClear.addEventListener('click', () => {
  conversationHistory = [];
  messagesArea.innerHTML = '';
  messagesArea.appendChild(buildWelcomeState());
  setStatus('idle', 'Ready');
});

function buildWelcomeState() {
  const existing = document.getElementById('welcome-state');
  if (existing) return existing;
  const div = document.createElement('div');
  div.id = 'welcome-state';
  div.className = 'welcome-state';
  div.innerHTML = welcomeState ? welcomeState.innerHTML : '';
  return div;
}

// ── Input handling ─────────────────────────────────────────────────────────────
userInput.addEventListener('input', () => {
  // Auto-resize
  userInput.style.height = 'auto';
  userInput.style.height = Math.min(userInput.scrollHeight, 120) + 'px';
  // Enable/disable send
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

// ── Core submit flow ──────────────────────────────────────────────────────────
async function submitQuestion(question) {
  if (isLoading || !question) return;

  // Hide welcome state
  const ws = document.getElementById('welcome-state');
  if (ws) ws.remove();

  // Render user bubble
  appendUserMessage(question);

  // Update history
  conversationHistory.push({ role: 'user', content: question });

  // Clear input
  userInput.value = '';
  userInput.style.height = 'auto';
  sendBtn.disabled = true;

  // Show thinking indicator
  const thinkingEl = appendThinking();
  setStatus('loading', 'Thinking…');
  isLoading = true;

  try {
    const response = await fetch(`${API_BASE_URL}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        question,
        history: conversationHistory.slice(-12), // bounded context
      }),
    });

    thinkingEl.remove();

    if (!response.ok) {
      const err = await response.json().catch(() => ({ detail: 'Unknown error' }));
      throw new Error(err.detail || `HTTP ${response.status}`);
    }

    const data = await response.json();

    // Render agent reply
    appendAgentMessage(data);

    // Update history with assistant reply
    conversationHistory.push({ role: 'assistant', content: data.answer });

    setStatus('ok', 'Ready');

  } catch (err) {
    thinkingEl.remove();
    appendErrorMessage(err.message || 'Something went wrong. Please try again.');
    setStatus('error', 'Error');
    setTimeout(() => setStatus('idle', 'Ready'), 3000);
  } finally {
    isLoading = false;
    sendBtn.disabled = !userInput.value.trim();
    scrollToBottom();
  }
}

// ── Message rendering helpers ─────────────────────────────────────────────────

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
  avatar.textContent = '✦';

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
    const caveatsEl = buildCaveatsEl(data.data_quality_notes);
    body.appendChild(caveatsEl);
  }

  // Partial failure warning
  if (data.partial_failure && data.partial_failure_reason) {
    const warn = document.createElement('div');
    warn.className = 'caveats-toggle';
    warn.style.background = 'rgba(239,68,68,0.1)';
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
  avatar.textContent = '✦';

  const body = document.createElement('div');
  body.className = 'msg-body';

  const bubble = document.createElement('div');
  bubble.className = 'msg-bubble';
  bubble.style.borderColor = 'rgba(239,68,68,0.3)';
  bubble.style.background = 'rgba(239,68,68,0.08)';
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
  avatar.textContent = '✦';

  const body = document.createElement('div');
  body.className = 'msg-body';

  const indicator = document.createElement('div');
  indicator.className = 'thinking-indicator';
  indicator.setAttribute('aria-label', 'Thinking');
  indicator.innerHTML = `
    <div class="thinking-dots" aria-hidden="true">
      <div class="thinking-dot"></div>
      <div class="thinking-dot"></div>
      <div class="thinking-dot"></div>
    </div>
    <span>Querying live data…</span>
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

// ── UI helpers ────────────────────────────────────────────────────────────────

function setStatus(state, text) {
  statusDot.className = `status-dot status-${state}`;
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

/**
 * Minimal markdown-to-HTML: bold, italic, inline code, bullets, newlines.
 * Good enough for LLM output without pulling in a full library.
 */
function formatMarkdown(text) {
  return escapeHtml(text)
    // Bold
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    // Italic
    .replace(/\*(.*?)\*/g, '<em>$1</em>')
    // Inline code
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    // Bullet points (- or * at line start)
    .replace(/^[•\-\*] (.+)$/gm, '<li>$1</li>')
    // Wrap consecutive <li> in <ul>
    .replace(/(<li>.*<\/li>\n?)+/g, m => `<ul>${m}</ul>`)
    // Section headers (### or **)
    .replace(/^#{3,4} (.+)$/gm, '<h4>$1</h4>')
    // Double newlines → paragraph breaks
    .replace(/\n\n+/g, '</p><p>')
    // Single newlines → <br>
    .replace(/\n/g, '<br>')
    // Wrap in paragraph if no block elements
    .replace(/^(?!<[uolh])(.+)/, '<p>$1</p>');
}

// ── Init ──────────────────────────────────────────────────────────────────────
userInput.focus();
