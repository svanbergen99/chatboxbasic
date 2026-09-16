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

const chats = {
  '1': {
    name: 'Operator',
    role: 'Chatbox 1 · Beheer',
    tagline: 'Algemene KCD-operator.',
    placeholder: 'Typ je bericht aan Operator...',
    endpoint: './api/chat/1',
    icon: 'fa-robot',
    avatarClass: 'aero-avatar',
    messageClass: 'aero',
  },
  '2': {
    name: 'Beveiliging & Creator',
    role: 'Chatbox 2 · Beheer',
    tagline: 'Beveiliging en creatieve taken.',
    placeholder: 'Typ je bericht aan Beveiliging & Creator...',
    endpoint: './api/chat/2',
    icon: 'fa-shield-halved',
    avatarClass: 'diva-avatar',
    messageClass: 'diva',
  },
};

let activeChat = localStorage.getItem('kcd_active_chat') || '1';
if (!chats[activeChat]) activeChat = '1';
let busy = false;
let typingRow = null;

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

function key(chatId) {
  return `kcd_chat_history_${chatId}`;
}

function load(chatId) {
  try {
    return JSON.parse(localStorage.getItem(key(chatId)) || '[]');
  } catch {
    return [];
  }
}

function save(chatId, items) {
  localStorage.setItem(key(chatId), JSON.stringify(items.slice(-200)));
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

function add(role, text, persist = true, time = now(), chatId = activeChat) {
  const config = chats[chatId] || chats['1'];
  const row = document.createElement('div');
  row.className = `message-row ${role === 'me' ? 'user' : 'bot'}`;

  const avatar = document.createElement('div');
  avatar.className = role === 'me'
    ? 'message-avatar user-icon'
    : `message-avatar bot ${config.messageClass}`;
  avatar.innerHTML = role === 'me'
    ? '<i class="fa-regular fa-user"></i>'
    : `<i class="fa-solid ${config.icon}"></i>`;

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
    const items = load(chatId);
    items.push({ role, text, time });
    save(chatId, items);
  }

  return row;
}

function render() {
  chat.innerHTML = '';
  const config = chats[activeChat];
  const items = load(activeChat);

  if (!items.length) {
    const empty = document.createElement('div');
    empty.className = 'empty-state';
    empty.innerHTML = `<div><h3>Start een gesprek met ${config.name}</h3><p>${config.role}. Druk op Enter om te verzenden. Shift + Enter maakt een nieuwe regel.</p></div>`;
    chat.appendChild(empty);
    scrollToBottom();
    return;
  }

  for (const message of items) {
    add(message.role, message.text, false, message.time || '', activeChat);
  }
  scrollToBottom();
}

function selectChat(chatId) {
  const config = chats[chatId];
  if (!config) return;

  activeChat = chatId;
  localStorage.setItem('kcd_active_chat', chatId);

  contacts.forEach((contact) => {
    contact.classList.toggle('active', contact.dataset.chatId === chatId);
  });

  headerName.textContent = config.name;
  headerTagline.textContent = config.tagline;
  headerAvatar.className = `assistant-avatar large ${config.avatarClass}`;
  headerAvatar.innerHTML = `<i class="fa-solid ${config.icon}"></i>`;
  input.placeholder = config.placeholder;

  render();
  updateHeaderStatus();
  input.focus();
}

function setStatus(chatId, online) {
  const dot = document.getElementById(`dot-chat-${chatId}`);
  const label = document.getElementById(`status-chat-${chatId}`);

  if (dot) {
    dot.classList.toggle('online', online);
    dot.classList.toggle('offline', !online);
  }
  if (label) label.textContent = online ? 'Online' : 'Offline';
  if (chatId === activeChat) updateHeaderStatus();
}

function updateHeaderStatus() {
  const label = document.getElementById(`status-chat-${activeChat}`);
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
      Object.keys(chats).forEach(id => setStatus(id, false));
      return;
    }

    Object.keys(chats).forEach(id => {
      setStatus(id, !!data.chatboxes?.[id]?.online);
    });
  } catch {
    Object.keys(chats).forEach(id => setStatus(id, false));
  }
}

function showTyping() {
  removeTyping();
  const config = chats[activeChat];
  const row = document.createElement('div');
  row.className = 'message-row bot typing-row';
  row.innerHTML = `
    <div class="message-avatar bot ${config.messageClass}">
      <i class="fa-solid ${config.icon}"></i>
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
  contact.addEventListener('click', () => selectChat(contact.dataset.chatId));
});

if (search) {
  search.addEventListener('input', () => {
    const query = search.value.trim().toLowerCase();
    contacts.forEach((contact) => {
      const config = chats[contact.dataset.chatId];
      const text = `${config?.name || ''} ${config?.role || ''}`.toLowerCase();
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
    const config = chats[activeChat];
    if (!config?.endpoint) throw new Error('Geen chatroute ingesteld.');

    const response = await fetch(config.endpoint, {
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

selectChat(activeChat);
checkStatus();
setInterval(checkStatus, 15000);
