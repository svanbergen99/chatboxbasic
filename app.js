const chat = document.getElementById('chat');
const form = document.getElementById('form');
const input = document.getElementById('message');
const sendBtn = document.getElementById('sendBtn');
const contacts = [...document.querySelectorAll('.assistant-card')];
const headerName = document.getElementById('headerName');
const headerAvatar = document.getElementById('headerAvatar');
const headerStatus = document.getElementById('headerStatus');
const headerTagline = document.getElementById('headerTagline');
const search = document.getElementById('contactSearch');

let activeAgent = localStorage.getItem('chatboxbasic_agent') || 'Aero';
let busy = false;
let typingRow = null;

const roles = {
  Aero: 'PC & algemene assistent',
  Diva: 'Creatieve assistent',
};

const taglines = {
  Aero: 'Helpt je denken, plannen en doen.',
  Diva: 'Helpt je creëren, verkennen en uitwerken.',
};

const chatRoutes = {
  Aero: './api/chat/1',
  Diva: './api/chat/2',
};

const DEVICE_KEY = 'chatboxbasic_device_id';

function makeDeviceId() {
  if (window.crypto && crypto.randomUUID) return crypto.randomUUID();
  return 'dev-' + Date.now().toString(36) + '-' + Math.random().toString(36).slice(2, 14);
}

function getDeviceId() {
  let id = localStorage.getItem(DEVICE_KEY);
  if (!id) {
    id = makeDeviceId();
    localStorage.setItem(DEVICE_KEY, id);
  }
  return id;
}

const DEVICE_ID = getDeviceId();
function apiHeaders(extra = {}) {
  return { 'X-Device-ID': DEVICE_ID, ...extra };
}

function key(agent) {
  return `chatboxbasic_history_${agent.toLowerCase()}`;
}

function load(agent) {
  try {
    return JSON.parse(localStorage.getItem(key(agent)) || '[]');
  } catch {
    return [];
  }
}

function save(agent, items) {
  localStorage.setItem(key(agent), JSON.stringify(items.slice(-200)));
}

function now() {
  return new Date().toLocaleTimeString('nl-NL', { hour: '2-digit', minute: '2-digit' });
}

function scrollToBottom(force = true) {
  requestAnimationFrame(() => {
    const nearBottom = chat.scrollHeight - chat.scrollTop - chat.clientHeight < 160;
    if (force || nearBottom) chat.scrollTop = chat.scrollHeight;
  });
}

function iconFor(agent) {
  return agent === 'Diva' ? 'fa-wand-magic-sparkles' : 'fa-robot';
}

function add(role, text, persist = true, time = now(), agent = activeAgent) {
  const row = document.createElement('div');
  row.className = `message-row ${role === 'me' ? 'user' : 'bot'}`;

  const avatar = document.createElement('div');
  avatar.className = role === 'me'
    ? 'message-avatar user-icon'
    : `message-avatar bot ${agent === 'Diva' ? 'diva' : 'aero'}`;
  avatar.innerHTML = role === 'me'
    ? '<i class="fa-regular fa-user"></i>'
    : `<i class="fa-solid ${iconFor(agent)}"></i>`;

  const body = document.createElement('div');
  body.className = 'message-body';

  const bubble = document.createElement('div');
  bubble.className = 'message-bubble';
  bubble.textContent = text;

  const meta = document.createElement('div');
  meta.className = 'message-meta';
  meta.textContent = time;

  body.appendChild(bubble);
  body.appendChild(meta);
  row.appendChild(avatar);
  row.appendChild(body);
  chat.appendChild(row);
  scrollToBottom();

  if (persist) {
    const items = load(agent);
    items.push({ role, text, time });
    save(agent, items);
  }

  return row;
}

function render() {
  chat.innerHTML = '';
  const items = load(activeAgent);

  if (!items.length) {
    const empty = document.createElement('div');
    empty.className = 'empty-state';
    empty.innerHTML = `<div><h3>Start een gesprek met ${activeAgent}</h3><p>Druk op Enter om te verzenden. Shift + Enter maakt een nieuwe regel.</p></div>`;
    chat.appendChild(empty);
    scrollToBottom();
    return;
  }

  for (const message of items) {
    add(message.role, message.text, false, message.time || '', activeAgent);
  }
  scrollToBottom();
}

function selectAgent(agent) {
  activeAgent = agent;
  localStorage.setItem('chatboxbasic_agent', agent);

  contacts.forEach((contact) => {
    contact.classList.toggle('active', contact.dataset.agent === agent);
  });

  headerName.textContent = agent;
  headerTagline.textContent = taglines[agent] || roles[agent] || '';
  headerAvatar.className = `assistant-avatar large ${agent === 'Diva' ? 'diva-avatar' : 'aero-avatar'}`;
  headerAvatar.innerHTML = `<i class="fa-solid ${iconFor(agent)}"></i>`;
  input.placeholder = `Typ je bericht aan ${agent}...`;

  render();
  updateHeaderStatus();
  input.focus();
}

function setStatus(agent, online) {
  const dot = document.getElementById(`dot-${agent}`);
  const label = document.getElementById(`status-${agent}`);

  if (dot) {
    dot.classList.toggle('online', online);
    dot.classList.toggle('offline', !online);
  }
  if (label) label.textContent = online ? 'Online' : 'Offline';
  if (agent === activeAgent) updateHeaderStatus();
}

function updateHeaderStatus() {
  const label = document.getElementById(`status-${activeAgent}`);
  headerStatus.textContent = label ? label.textContent : 'Onbekend';
}

async function checkStatus() {
  try {
    const response = await fetch('./api/status', {
      cache: 'no-store',
      headers: apiHeaders(),
    });
    if (!response.ok) throw new Error('lokale backend niet bereikbaar');

    const data = await response.json();
    if (data.deviceSecurity && data.deviceAllowed === false) {
      setStatus('Aero', false);
      setStatus('Diva', false);
      return;
    }

    setStatus('Aero', !!data.Aero);
    setStatus('Diva', !!data.Diva);
  } catch {
    setStatus('Aero', false);
    setStatus('Diva', false);
  }
}

function showTyping() {
  removeTyping();
  const row = document.createElement('div');
  row.className = 'message-row bot typing-row';
  row.innerHTML = `
    <div class="message-avatar bot ${activeAgent === 'Diva' ? 'diva' : 'aero'}">
      <i class="fa-solid ${iconFor(activeAgent)}"></i>
    </div>
    <div class="message-body">
      <div class="message-bubble">
        <span class="typing-dot"></span>
        <span class="typing-dot"></span>
        <span class="typing-dot"></span>
      </div>
    </div>`;
  typingRow = row;
  chat.appendChild(row);
  scrollToBottom();
}

function removeTyping() {
  if (typingRow && typingRow.parentNode) typingRow.remove();
  typingRow = null;
}

contacts.forEach((contact) => {
  contact.addEventListener('click', () => selectAgent(contact.dataset.agent));
});

if (search) {
  search.addEventListener('input', () => {
    const query = search.value.trim().toLowerCase();
    contacts.forEach((contact) => {
      const agent = contact.dataset.agent || '';
      const text = `${agent} ${roles[agent] || ''}`.toLowerCase();
      contact.hidden = query ? !text.includes(query) : false;
    });
  });
}

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  if (busy) return;

  const raw = input.value.trim();
  if (!raw) return;

  input.value = '';
  input.style.height = 'auto';
  add('me', raw);

  busy = true;
  sendBtn.disabled = true;
  showTyping();

  try {
    const endpoint = chatRoutes[activeAgent];
    if (!endpoint) throw new Error('Geen chatroute ingesteld.');

    const response = await fetch(endpoint, {
      method: 'POST',
      headers: apiHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({ message: raw }),
    });

    if (response.status === 403) {
      const data = await response.json().catch(() => ({}));
      throw new Error(data.error || 'Dit apparaat is niet goedgekeurd.');
    }

    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.error || `backend ${response.status}`);

    const reply = data.reply || data.error || '';
    if (!reply) throw new Error('Geen antwoord ontvangen.');

    removeTyping();
    add('bot', reply);
  } catch (error) {
    removeTyping();
    add('bot', 'Fout: ' + error.message);
  } finally {
    busy = false;
    sendBtn.disabled = false;
    checkStatus();
    input.focus();
    scrollToBottom();
  }
});

input.addEventListener('keydown', (event) => {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault();
    form.requestSubmit();
  }
});

input.addEventListener('input', () => {
  input.style.height = 'auto';
  input.style.height = Math.min(input.scrollHeight, 180) + 'px';
});

selectAgent(activeAgent);
checkStatus();
setInterval(checkStatus, 15000);
