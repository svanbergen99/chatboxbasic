const chat=document.getElementById('chat');
const form=document.getElementById('form');
const input=document.getElementById('message');
const contacts=[...document.querySelectorAll('.contact')];
const headerName=document.getElementById('headerName');
const headerAvatar=document.getElementById('headerAvatar');
const headerStatus=document.getElementById('headerStatus');
const headerRole=document.getElementById('headerRole');
const search=document.getElementById('contactSearch');
let activeAgent=localStorage.getItem('chatboxbasic_agent')||'Aero';
let busy=false;

const roles={Aero:'PC & algemene assistent',Diva:'Creatieve assistent'};
const TEST_API='https://catfact.ninja/fact';
function key(agent){return `chatboxbasic_history_${agent.toLowerCase()}`}
function load(agent){try{return JSON.parse(localStorage.getItem(key(agent))||'[]')}catch{return []}}
function save(agent,items){localStorage.setItem(key(agent),JSON.stringify(items.slice(-200)))}
function now(){return new Date().toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'})}
function add(role,text,persist=true,time=now()){
  const row=document.createElement('div');row.className='msg-row '+(role==='me'?'me':'bot');
  const bubble=document.createElement('div');bubble.className='msg';
  const body=document.createElement('div');body.textContent=text;bubble.appendChild(body);
  const meta=document.createElement('span');meta.className='msg-meta';meta.textContent=time;bubble.appendChild(meta);
  row.appendChild(bubble);chat.appendChild(row);chat.scrollTop=chat.scrollHeight;
  if(persist){const items=load(activeAgent);items.push({role,text,time});save(activeAgent,items)}
  return row;
}
function render(){
  chat.innerHTML='';const items=load(activeAgent);
  if(!items.length){const empty=document.createElement('div');empty.className='empty';empty.textContent=`Begin een gesprek met ${activeAgent}.`;chat.appendChild(empty);return}
  for(const m of items)add(m.role,m.text,false,m.time||'');
}
function selectAgent(agent){
  activeAgent=agent;localStorage.setItem('chatboxbasic_agent',agent);
  contacts.forEach(c=>c.classList.toggle('active',c.dataset.agent===agent));
  headerName.textContent=agent;headerRole.textContent=roles[agent]||'';headerAvatar.textContent=agent[0];
  headerAvatar.className='avatar '+(agent==='Diva'?'diva-avatar':'aero-avatar');
  input.placeholder=`Typ een bericht aan ${agent}...`;render();updateHeaderStatus();input.focus();
}
function setStatus(agent,online){
  const dot=document.getElementById(`dot-${agent}`);const label=document.getElementById(`status-${agent}`);
  if(dot){dot.classList.toggle('online',online);dot.classList.toggle('offline',!online)}
  if(label)label.textContent=online?'online':'offline';
  if(agent===activeAgent)updateHeaderStatus();
}
function updateHeaderStatus(){
  const label=document.getElementById(`status-${activeAgent}`);headerStatus.textContent=label?label.textContent:'onbekend';
  headerStatus.style.color=headerStatus.textContent==='online'?'#059669':'#9ca3af';
}
async function publicApiReply(){
  const r=await fetch(TEST_API,{cache:'no-store'});
  if(!r.ok)throw new Error(`Test-API ${r.status}`);
  const j=await r.json();
  return `Test-API werkt. ${j.fact||'Antwoord ontvangen.'}`;
}
async function checkStatus(){
  try{
    const r=await fetch('/api/status',{cache:'no-store'});
    if(!r.ok)throw new Error('lokale backend niet bereikbaar');
    const j=await r.json();setStatus('Aero',!!j.Aero);setStatus('Diva',!!j.Diva);return;
  }catch{}
  try{await fetch(TEST_API,{cache:'no-store'});setStatus('Aero',true);setStatus('Diva',false)}
  catch{setStatus('Aero',false);setStatus('Diva',false)}
}
contacts.forEach(c=>c.addEventListener('click',()=>selectAgent(c.dataset.agent)));
if(search){search.addEventListener('input',()=>{const q=search.value.trim().toLowerCase();contacts.forEach(c=>{c.style.display=(c.dataset.agent.toLowerCase().includes(q)||(roles[c.dataset.agent]||'').toLowerCase().includes(q))?'flex':'none'})})}
form.addEventListener('submit',async e=>{
  e.preventDefault();if(busy)return;const raw=input.value.trim();if(!raw)return;
  input.value='';add('me',raw);busy=true;form.querySelector('.send-btn').disabled=true;
  const wait=add('bot','Even nadenken...',false);
  const outgoing=activeAgent==='Diva'&&!/^diva[: ]/i.test(raw)?`Diva: ${raw}`:raw;
  try{
    let reply='';
    try{
      const r=await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:outgoing})});
      if(!r.ok)throw new Error(`backend ${r.status}`);
      const j=await r.json();reply=j.reply||j.error||'';
      if(!reply)throw new Error('geen antwoord');
    }catch{
      reply=await publicApiReply();
    }
    wait.remove();add('bot',reply);
  }
  catch(err){wait.remove();add('bot','Fout: '+err.message)}
  finally{busy=false;form.querySelector('.send-btn').disabled=false;checkStatus();input.focus()}
});
input.addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();form.requestSubmit()}});
input.addEventListener('input',()=>{input.style.height='auto';input.style.height=Math.min(input.scrollHeight,140)+'px'});
selectAgent(activeAgent);checkStatus();setInterval(checkStatus,15000);
