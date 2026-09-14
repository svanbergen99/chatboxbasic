const chat=document.getElementById('chat');
const form=document.getElementById('form');
const input=document.getElementById('message');
const contacts=[...document.querySelectorAll('.contact')];
const headerName=document.getElementById('headerName');
const headerAvatar=document.getElementById('headerAvatar');
const headerStatus=document.getElementById('headerStatus');
let activeAgent=localStorage.getItem('chatboxbasic_agent')||'Aero';
let busy=false;

function key(agent){return `chatboxbasic_history_${agent.toLowerCase()}`}
function load(agent){try{return JSON.parse(localStorage.getItem(key(agent))||'[]')}catch{return []}}
function save(agent,items){localStorage.setItem(key(agent),JSON.stringify(items.slice(-200)))}
function add(role,text,persist=true){
  const row=document.createElement('div');row.className='msg-row '+(role==='me'?'me':'bot');
  const bubble=document.createElement('div');bubble.className='msg';bubble.textContent=text;row.appendChild(bubble);chat.appendChild(row);
  chat.scrollTop=chat.scrollHeight;
  if(persist){const items=load(activeAgent);items.push({role,text});save(activeAgent,items)}
  return row;
}
function render(){
  chat.innerHTML='';const items=load(activeAgent);
  if(!items.length){const empty=document.createElement('div');empty.className='empty';empty.textContent=`Begin een gesprek met ${activeAgent}.`;chat.appendChild(empty);return}
  for(const m of items)add(m.role,m.text,false);
}
function selectAgent(agent){
  activeAgent=agent;localStorage.setItem('chatboxbasic_agent',agent);
  contacts.forEach(c=>c.classList.toggle('active',c.dataset.agent===agent));
  headerName.textContent=agent;headerAvatar.textContent=agent[0];headerAvatar.classList.toggle('diva',agent==='Diva');
  input.placeholder=`Typ een bericht aan ${agent}...`;render();updateHeaderStatus();input.focus();
}
function setStatus(agent,online){
  const dot=document.getElementById(`dot-${agent}`);const label=document.getElementById(`status-${agent}`);
  dot.classList.toggle('online',online);dot.classList.toggle('offline',!online);label.textContent=online?'online':'offline';
  if(agent===activeAgent)updateHeaderStatus();
}
function updateHeaderStatus(){
  const label=document.getElementById(`status-${activeAgent}`);headerStatus.textContent=label?label.textContent:'onbekend';
}
async function checkStatus(){
  try{const r=await fetch('/api/status',{cache:'no-store'});const j=await r.json();setStatus('Aero',!!j.Aero);setStatus('Diva',!!j.Diva)}
  catch{setStatus('Aero',false);setStatus('Diva',false)}
}
contacts.forEach(c=>c.addEventListener('click',()=>selectAgent(c.dataset.agent)));
form.addEventListener('submit',async e=>{
  e.preventDefault();if(busy)return;const raw=input.value.trim();if(!raw)return;
  input.value='';add('me',raw);busy=true;form.querySelector('button').disabled=true;
  const wait=add('bot','...',false);
  const outgoing=activeAgent==='Diva'&&!/^diva[: ]/i.test(raw)?`Diva: ${raw}`:raw;
  try{const r=await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:outgoing})});const j=await r.json();wait.remove();add('bot',j.reply||j.error||'Geen antwoord.')}
  catch(err){wait.remove();add('bot','Fout: '+err.message)}
  finally{busy=false;form.querySelector('button').disabled=false;checkStatus();input.focus()}
});
input.addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();form.requestSubmit()}});
selectAgent(activeAgent);checkStatus();setInterval(checkStatus,15000);
