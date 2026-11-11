/* CMTI help-desk chat widget.
   Embed on any page with:
     <script src="https://YOUR-BACKEND/widget.js" defer></script>
   Optional attributes on that script tag:
     data-api="https://YOUR-BACKEND"   backend address (defaults to where widget.js was loaded from)
     data-open="true"                  open the chat panel immediately
   The browser only talks to our backend; the API key never reaches it. */
(() => {
  const script = document.currentScript;
  const API = (script?.dataset.api || new URL(script?.src || location.href).origin).replace(/\/$/, '');
  const START_OPEN = script?.dataset.open === 'true';
  const STORE_KEY = 'cmti-chat-session';

  const css = document.createElement('link');
  css.rel = 'stylesheet';
  css.href = API + '/widget.css';
  document.head.append(css);

  const el = (tag, cls, text) => {
    const node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text) node.textContent = text;
    return node;
  };

  const root = el('div', 'cmti-chat');
  root.innerHTML = `
    <button class="cc-launch" type="button" aria-expanded="false" aria-controls="cc-panel">
      <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 5h16v11H8l-4 4V5Z"/></svg><span>Ask CMTI</span>
    </button>
    <section class="cc-panel" id="cc-panel" role="dialog" aria-label="CMTI help desk chat" hidden>
      <header class="cc-head">
        <div><strong>Aakruti</strong><span>CMTI help desk assistant</span></div>
        <button class="cc-new" type="button" title="Start a new chat">New chat</button>
        <button class="cc-close" type="button" aria-label="Close chat">×</button>
      </header>
      <p class="cc-notice">AI assistant. Your messages are sent to an external AI service (Google Gemini) to generate replies. Please don't share personal details such as your name, phone number or USN.</p>
      <div class="cc-log" role="log" aria-live="polite"></div>
      <form class="cc-form">
        <label class="cc-sr" for="cc-input">Your question</label>
        <textarea id="cc-input" rows="1" maxlength="1000" placeholder="Ask a question about CMTI…"></textarea>
        <button type="submit" aria-label="Send">
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 20 21 12 3 4v6l12 2-12 2v6Z"/></svg>
        </button>
      </form>
    </section>`;
  document.body.append(root);

  const launch = root.querySelector('.cc-launch');
  const panel = root.querySelector('.cc-panel');
  const log = root.querySelector('.cc-log');
  const form = root.querySelector('.cc-form');
  const input = root.querySelector('#cc-input');
  const sendBtn = form.querySelector('button');

  let sessionId = null;
  try { sessionId = localStorage.getItem(STORE_KEY); } catch (_) { /* storage blocked */ }
  const saveSession = (id) => { sessionId = id; try { localStorage.setItem(STORE_KEY, id); } catch (_) {} };

  const WELCOME = "Hello! I'm Aakruti, CMTI's help-desk assistant. I can answer questions about our certified courses (CACM and IDM), corporate training, college MoUs, e-learning and webinars, and how to contact CMTI. How can I help you?";

  function addBubble(role, text, messageId) {
    const row = el('div', 'cc-msg cc-' + role);
    row.append(el('p', 'cc-bubble', text));
    if (role === 'bot' && messageId) {
      const fb = el('div', 'cc-fb');
      for (const [rating, label, symbol] of [[1, 'Helpful', '👍'], [-1, 'Not helpful', '👎']]) {
        const b = el('button', '', symbol);
        b.type = 'button';
        b.setAttribute('aria-label', label);
        b.addEventListener('click', async () => {
          fb.querySelectorAll('button').forEach((x) => x.setAttribute('aria-pressed', String(x === b)));
          try {
            await fetch(API + '/api/feedback', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ message_id: messageId, rating }) });
          } catch (_) { /* feedback is best effort */ }
        });
        fb.append(b);
      }
      row.append(fb);
    }
    log.append(row);
    log.scrollTop = log.scrollHeight;
    return row;
  }

  function showWelcome() { log.innerHTML = ''; addBubble('bot', WELCOME); }

  async function loadHistory() {
    if (!sessionId) return showWelcome();
    try {
      const res = await fetch(API + '/api/history/' + encodeURIComponent(sessionId));
      const data = await res.json();
      showWelcome();
      for (const m of data.messages || []) addBubble(m.role, m.content, m.role === 'bot' ? m.message_id : null);
    } catch (_) { showWelcome(); }
  }

  function setOpen(open) {
    panel.hidden = !open;
    launch.setAttribute('aria-expanded', String(open));
    root.classList.toggle('is-open', open);
    if (open) { if (!log.children.length) loadHistory(); setTimeout(() => input.focus(), 50); }
  }

  launch.addEventListener('click', () => setOpen(panel.hidden));
  root.querySelector('.cc-close').addEventListener('click', () => { setOpen(false); launch.focus(); });
  panel.addEventListener('keydown', (e) => { if (e.key === 'Escape') { setOpen(false); launch.focus(); } });

  root.querySelector('.cc-new').addEventListener('click', async () => {
    try {
      const res = await fetch(API + '/api/reset/' + encodeURIComponent(sessionId || 'new'), { method: 'POST' });
      saveSession((await res.json()).session_id);
    } catch (_) { sessionId = null; try { localStorage.removeItem(STORE_KEY); } catch (__) {} }
    showWelcome();
    input.focus();
  });

  input.addEventListener('input', () => { input.style.height = 'auto'; input.style.height = Math.min(input.scrollHeight, 120) + 'px'; });
  input.addEventListener('keydown', (e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); form.requestSubmit(); } });

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const text = input.value.trim();
    if (!text) { input.focus(); return; }
    addBubble('user', text);
    input.value = '';
    input.style.height = 'auto';
    sendBtn.disabled = true;
    const typing = addBubble('bot', '');
    typing.classList.add('cc-typing');
    typing.querySelector('.cc-bubble').innerHTML = '<span></span><span></span><span></span>';
    typing.setAttribute('aria-label', 'Aakruti is typing');
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 30000);
    try {
      const res = await fetch(API + '/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId, message: text }),
        signal: controller.signal,
      });
      const data = await res.json().catch(() => ({}));
      typing.remove();
      if (!res.ok) { addBubble('error', data.error || 'Something went wrong. Please try again.'); return; }
      saveSession(data.session_id);
      addBubble('bot', data.reply, data.message_id);
    } catch (err) {
      typing.remove();
      addBubble('error', err.name === 'AbortError'
        ? 'The reply is taking too long. Please try again.'
        : "I can't reach the CMTI assistant right now. Please check your connection, or contact cmtioffice@cmti.co.in.");
    } finally {
      clearTimeout(timer);
      sendBtn.disabled = false;
      input.focus();
    }
  });

  if (START_OPEN) setOpen(true);
})();
