'use strict';
const $=id=>document.getElementById(id);
const feed=$('feed'), viewport=$('viewport'), canvas=$('overlay'), ctx=canvas.getContext('2d');
let csrf='', state=null, lastLog=0, sequence=-1, lastProgress=performance.now(), lastReply=performance.now();
let stream=false, busy=false, editing=null, drag=null, sessionEnded=false, active='setup', terminalBusy=false;
let setupRows=[], setupActions=[], setupBusy=false;
const terminals=new Map();
function log(level,message,timestamp=new Date().toISOString()){
 const box=$('logs'),follow=box.scrollHeight-box.scrollTop-box.clientHeight<32;
 const row=document.createElement('div');row.className='line';
 const time=document.createElement('span');time.className='time';time.textContent=timestamp+' ';
 const text=document.createElement('span');text.className=level;text.textContent=level.toUpperCase()+' '+message;
 row.append(time,text);box.append(row);while(box.childElementCount>300)box.firstElementChild.remove();if(follow)box.scrollTop=box.scrollHeight;
}
async function api(path,method='GET',body){
 const response=await fetch(path,{method,headers:{'Content-Type':'application/json','X-CSRF-Token':csrf},body:body===undefined?undefined:JSON.stringify(body),signal:AbortSignal.timeout(6000)});
 if(response.status===401){sessionEnded=true;location.replace('/login');throw Error('Anmeldung erforderlich');}
 if(!response.ok){let message=await response.text();try{message=JSON.parse(message).error||message;}catch(_){}throw Error(message);}
 return response.json();
}
async function command(op,args={}){return api('/command','POST',{op,args});}
function disconnect(){if(!editing){feed.hidden=true;feed.removeAttribute('src');$('empty').hidden=false;}stream=false;$('metrics').textContent='—';$('status').textContent='offline';$('status').className='';}
feed.onerror=()=>{if(!editing && feed.hasAttribute('src'))disconnect();};
$('clear').onclick=()=>$('logs').replaceChildren();
$('logout').onclick=async()=>{try{await api('/logout','POST',{});sessionEnded=true;for(const t of terminals.values())t.ws?.close();location.replace('/login');}catch(e){log('error',e.message);}};
async function poll(){
 if(busy || sessionEnded)return;busy=true;
 try{
  const s=await api('/status');state=s;csrf=s.csrf;lastReply=performance.now();
  if(sequence!==s.sequence){sequence=s.sequence;lastProgress=performance.now();}
  if(s.logs.length && s.logs.at(-1).id<lastLog)lastLog=0;
  for(const entry of s.logs)if(entry.id>lastLog){log(entry.level,entry.message,entry.timestamp);lastLog=entry.id;}
  $('mode').textContent='/ '+s.mode+(editing?' / frozen':'');
  if(s.live && performance.now()-lastProgress<2000){
   if(!editing){if(!stream){feed.src='/stream.mjpg?t='+Date.now();stream=true;}feed.hidden=false;$('empty').hidden=true;}
   $('status').textContent=s.simulated?'simulated':s.mode;$('status').className='live';
   $('metrics').textContent=`#${s.sequence} · ${s.processing_fps} fps · ${s.profile}${s.dirty?' *':''}`;
  }else disconnect();
  if(s.setup)renderSetup(s.setup);
  syncTabs(s.terminals);
  if(!s.terminals.length && !terminalBusy){terminalBusy=true;try{await api('/terminals','POST',{});}finally{terminalBusy=false;}}
 }catch(e){disconnect();}finally{busy=false;}
}
/* Einstelltabelle: dieselben Zeilen und Aktionen wie dispread tui. */
function buildRow(row){
 const element=document.createElement('div');element.className='setup-row';element.dataset.key=row.key;element.tabIndex=-1;
 const name=document.createElement('span');name.className='name';name.textContent=row.label;
 const slot=document.createElement('span');slot.className='control';
 const hint=document.createElement('span');hint.className='hint';
 if(row.kind==='choice'){
  const select=document.createElement('select');select.ariaLabel=row.label;
  select.onchange=()=>apply(row.key,select.value);slot.append(select);
 }else if(row.kind==='number'){
  const input=document.createElement('input');input.type='number';input.ariaLabel=row.label;
  input.min=row.min;input.max=row.max;input.step=row.step;
  input.onchange=()=>apply(row.key,input.value);
  const presets=document.createElement('select');presets.className='presets';presets.ariaLabel=row.label+' Schnellwahl';
  presets.onchange=()=>{if(presets.value!=='')apply(row.key,presets.value);};
  slot.append(input,presets);
 }
 element.append(name,slot,hint);
 return element;
}
function updateRow(element,row){
 element.classList.toggle('locked',row.disabled);
 element.querySelector('.hint').textContent=(row.reason||row.hint)+(row.observed?' / ist '+row.observed:'');
 const slot=element.querySelector('.control');
 if(row.kind==='choice'){
  const select=slot.querySelector('select');
  if(document.activeElement===select)return;
  const signature=row.options.map(option=>[option.value,option.label,option.disabled?1:0].join(' ')).join('|');
  if(select.dataset.signature!==signature){
   select.replaceChildren(...row.options.map(option=>{
    const item=document.createElement('option');item.value=option.value;item.textContent=option.label;
    item.disabled=option.disabled;if(option.reason)item.title=option.reason;return item;}));
   select.dataset.signature=signature;
  }
  select.value=row.value;select.disabled=row.disabled;
 }else if(row.kind==='number'){
  const input=slot.querySelector('input'),presets=slot.querySelector('.presets');
  const signature=row.presets.map(preset=>preset.label).join('|');
  if(presets.dataset.signature!==signature){
   presets.replaceChildren(...[{value:'',label:'schnellwahl'},...row.presets].map(preset=>{
    const item=document.createElement('option');item.value=preset.value;item.textContent=preset.label;return item;}));
   presets.dataset.signature=signature;
  }
  input.disabled=presets.disabled=row.disabled;
  if(document.activeElement!==input)input.value=row.value;
  if(document.activeElement!==presets)presets.value='';
 }else slot.textContent=row.display;
 if(row.kind!=='info')element.querySelector('.name').title=row.display;
}
function renderSetup(setup){
 setupRows=setup.rows;setupActions=setup.actions;
 const container=$('setup-rows');
 const present=[...container.children].map(child=>child.dataset.key).join(',');
 if(present!==setup.rows.map(row=>row.key).join(','))container.replaceChildren(...setup.rows.map(buildRow));
 for(const [index,row] of setup.rows.entries())updateRow(container.children[index],row);
 const bar=$('setup-actions');
 const signature=setup.actions.map(action=>[action.key,action.enabled?1:0].join(' ')).join('|');
 if(bar.dataset.signature!==signature){
  bar.replaceChildren(...setup.actions.map(action=>{
   const button=document.createElement('button');button.textContent=`[${action.hotkey}] ${action.label}`;
   button.disabled=!action.enabled;button.title=action.reason;button.onclick=()=>run(action);return button;}));
  bar.dataset.signature=signature;
 }
}
async function send(operations){
 if(setupBusy)return;setupBusy=true;
 try{for(const [op,args] of operations)await command(op,args);}
 catch(e){log('error',e.message);}
 finally{setupBusy=false;await poll();}
}
function apply(key,raw){
 const row=setupRows.find(entry=>entry.key===key);
 if(!row)return;
 if(row.kind==='choice'){
  const option=row.options.find(entry=>entry.value===raw);
  if(!option)return;
  if(option.disabled){log('warn',`${row.label}: ${option.reason}`);return;}
  return send(option.ops);
 }
 const value=row.integer?Math.round(Number(raw)):Number(raw);
 if(!Number.isFinite(value)||value<row.min||value>row.max){log('error',`${row.label}: erlaubt ${row.min} bis ${row.max}`);return;}
 return send([[row.op,{key:row.arg,value}]]);
}
function run(action){
 if(!action.enabled){log('warn',`${action.label}: ${action.reason}`);return;}
 if(action.needs_name){
  $('setup-name').hidden=false;$('name-input').value=state?state.profile:'';$('name-input').focus();$('name-input').select();return;
 }
 return send([[action.op,action.args]]);
}
$('name-cancel').onclick=()=>{$('setup-name').hidden=true;$('setup-pane').focus();};
$('name-ok').onclick=async()=>{
 const name=$('name-input').value.trim();
 $('setup-name').hidden=true;
 if(name)await send([['profile.save',{name}]]);
 $('setup-pane').focus();
};
$('name-input').onkeydown=event=>{
 if(event.key==='Enter'){event.preventDefault();$('name-ok').click();}
 if(event.key==='Escape'){event.preventDefault();$('name-cancel').click();}
};
$('setup-pane').onkeydown=event=>{
 const inside=/^(SELECT|INPUT)$/.test(event.target.tagName);
 const rows=[...$('setup-rows').children];
 const current=rows.findIndex(row=>row.contains(event.target));
 if(event.key==='ArrowDown'||event.key==='ArrowUp'){
  event.preventDefault();
  const step=event.key==='ArrowDown'?1:-1;
  const from=current<0?(step>0?-1:rows.length):current;
  rows[Math.max(0,Math.min(rows.length-1,from+step))]?.focus();
  return;
 }
 if(event.key==='Escape'&&inside){event.preventDefault();rows[current]?.focus();return;}
 if(inside)return;
 if(event.key==='Enter'){
  event.preventDefault();
  const element=rows[current]?.querySelector('.control select,.control input');
  if(!element||element.disabled)return;
  element.focus();try{element.showPicker?.();}catch(_){}
  return;
 }
 if(event.key.length===1&&!event.ctrlKey&&!event.altKey&&!event.metaKey){
  const action=setupActions.find(entry=>entry.hotkey===event.key.toLowerCase());
  if(action){event.preventDefault();run(action);}
 }
};
/* Shell-Tabs. */
function fit(t){if(t.id===active){try{t.fit.fit();if(t.ws?.readyState===1)t.ws.send(JSON.stringify({type:'resize',cols:t.term.cols,rows:t.term.rows}));}catch(_){}}}
function select(id){
 active=id;
 const setup=id==='setup';
 $('setup-pane').hidden=!setup;$('terminals').hidden=setup;$('setup-tab').classList.toggle('active',setup);
 for(const t of terminals.values()){t.pane.hidden=t.id!==id;t.button.classList.toggle('active',t.id===id);}
 if(setup){$('setup-pane').focus();return;}
 const t=terminals.get(id);if(t){fit(t);t.term.focus();}
}
$('setup-tab').onclick=()=>select('setup');
function connect(t){
 if(sessionEnded || !terminals.has(t.id))return;
 t.ws=new WebSocket(`wss://${location.host}/terminals/${t.id}/ws`);t.ws.binaryType='arraybuffer';
 t.ws.onopen=()=>fit(t);
 t.ws.onmessage=event=>{if(event.data instanceof ArrayBuffer)t.term.write(new Uint8Array(event.data));else{
  const data=JSON.parse(event.data);if(data.reset){t.term.reset();if(data.truncated)log('warn','Shell-Historie gekürzt; Ausgabe-Puffer ist begrenzt.');}
  if(data.exit_code!==undefined){t.exited=true;log('info',`Shell beendet: ${data.exit_code}`);}
 }};
 t.ws.onclose=()=>{if(!sessionEnded && terminals.has(t.id) && !t.exited)setTimeout(()=>connect(t),1200);};
}
function syncTabs(items){
 for(const [id,t] of terminals)if(!items.some(item=>item.id===id)){terminals.delete(id);t.ws?.close();t.term.dispose();t.pane.remove();t.tab.remove();}
 for(const [index,item] of items.entries()){
  if(terminals.has(item.id))continue;
  const pane=document.createElement('div');pane.className='terminal-pane';pane.hidden=true;$('terminals').append(pane);
  const tab=document.createElement('span'),button=document.createElement('button'),close=document.createElement('button');
  button.className='tab';button.textContent='shell '+(index+1);close.textContent='×';close.ariaLabel='Shell schließen';tab.append(button,close);$('tabs').append(tab);
  const term=new Terminal({fontFamily:'Consolas,monospace',fontSize:12,scrollback:3000,theme:{background:'#0b0d0f',foreground:'#c6ccd2'},allowProposedApi:false});
  const fitAddon=new FitAddon.FitAddon();term.loadAddon(fitAddon);term.open(pane);
  const t={id:item.id,pane,tab,button,term,fit:fitAddon,ws:null,exited:item.exit_code!==null};terminals.set(item.id,t);
  button.onclick=()=>select(item.id);close.onclick=async()=>{try{await api('/terminals/'+item.id,'DELETE');}catch(e){log('error',e.message);}};
  term.onData(data=>{if(t.ws?.readyState===1){const bytes=new TextEncoder().encode(data);for(let start=0;start<bytes.length;start+=8192)t.ws.send(bytes.slice(start,start+8192));}});
  connect(t);
 }
 if(active!=='setup' && !terminals.has(active))select(terminals.keys().next().value ?? 'setup');
}
$('plus').onclick=async()=>{if(terminalBusy)return;terminalBusy=true;try{const t=await api('/terminals','POST',{});const s=await api('/status');syncTabs(s.terminals);select(t.id);}catch(e){log('error',e.message);}finally{terminalBusy=false;}};
new ResizeObserver(()=>{for(const t of terminals.values())fit(t);draw();}).observe(viewport);
new ResizeObserver(()=>{for(const t of terminals.values())fit(t);}).observe($('terminals'));
/* Kamerabild einfrieren und Anzeigebereich setzen. */
async function freeze(){
 if(editing)return;
 try{editing=await command('freeze');feed.src='/frozen/'+editing.id+'.jpg';feed.hidden=false;$('empty').hidden=true;stream=false;canvas.hidden=false;viewport.focus();draw();
 log('info','Eingefrorenes Original: ziehen = verschieben, Ecke = Größe, Pfeile = korrigieren, Shift+Pfeile = Größe, Enter = bestätigen, Esc = verwerfen.');
 }catch(e){log('error',e.message);}
}
function draw(){
 if(!editing)return;
 const scale=Math.min(viewport.clientWidth/editing.width,viewport.clientHeight/editing.height);
 const w=Math.round(editing.width*scale),h=Math.round(editing.height*scale);
 canvas.width=w;canvas.height=h;canvas.style.width=w+'px';canvas.style.height=h+'px';canvas.style.left=(viewport.clientWidth-w)/2+'px';canvas.style.top=(viewport.clientHeight-h)/2+'px';
 const [x,y,rw,rh]=editing.roi;ctx.clearRect(0,0,w,h);ctx.strokeStyle='#a6d6a6';ctx.lineWidth=2;ctx.strokeRect(x*w,y*h,rw*w,rh*h);ctx.fillStyle='#a6d6a6';ctx.fillRect((x+rw)*w-5,(y+rh)*h-5,10,10);
}
function clamp(){const r=editing.roi;r[2]=Math.max(.01,Math.min(1,r[2]));r[3]=Math.max(.01,Math.min(1,r[3]));r[0]=Math.max(0,Math.min(1-r[2],r[0]));r[1]=Math.max(0,Math.min(1-r[3],r[1]));}
function point(event){const box=canvas.getBoundingClientRect();return [(event.clientX-box.left)/box.width,(event.clientY-box.top)/box.height];}
canvas.onpointerdown=event=>{if(!editing)return;canvas.setPointerCapture(event.pointerId);const [x,y]=point(event),r=editing.roi;drag={start:[x,y],roi:[...r],resize:Math.abs(x-r[0]-r[2])*canvas.width<15&&Math.abs(y-r[1]-r[3])*canvas.height<15};};
canvas.onpointermove=event=>{if(!drag)return;const [x,y]=point(event),dx=x-drag.start[0],dy=y-drag.start[1],r=[...drag.roi];if(drag.resize){r[2]+=dx;r[3]+=dy;}else{r[0]+=dx;r[1]+=dy;}editing.roi=r;clamp();draw();};
canvas.onpointerup=()=>drag=null;canvas.onpointercancel=()=>drag=null;
function unfreeze(){editing=null;drag=null;canvas.hidden=true;feed.removeAttribute('src');stream=false;poll();}
viewport.ondblclick=freeze;
viewport.onkeydown=async event=>{
 if(event.key==='e'&&!editing){event.preventDefault();await freeze();return;}
 if(!editing)return;
 if(event.key==='Escape'){event.preventDefault();unfreeze();return;}
 if(event.key==='Enter'){event.preventDefault();try{await command('roi',{id:editing.id,roi:editing.roi,role:state.config.role});unfreeze();}catch(e){log('error',e.message);}return;}
 const dir={ArrowLeft:[-1,0],ArrowRight:[1,0],ArrowUp:[0,-1],ArrowDown:[0,1]}[event.key];
 if(dir){event.preventDefault();const offset=event.shiftKey?2:0;editing.roi[offset]+=dir[0]/editing.width;editing.roi[offset+1]+=dir[1]/editing.height;clamp();draw();}
};
setInterval(()=>{if(!editing && (performance.now()-lastReply>2000||performance.now()-lastProgress>2000))disconnect();},250);
select('setup');
log('info','Einrichtung im setup-Tab: Werte auswählen, Tasten in Klammern lösen Aktionen aus. Kamerabereich mit E oder Doppelklick bearbeiten.');
setInterval(poll,500);poll();
