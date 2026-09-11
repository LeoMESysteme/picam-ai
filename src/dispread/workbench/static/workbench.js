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
  if(editing){editing.ocr_grid=s.ocr_grid;draw();}
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
  updateClipPanel(s.clip);
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
 try{
  editing=await command('freeze');
  editing.stage='roi';editing.mode='browse';editing.selected=null;
  editing.preEdit=null;editing.pending=null;editing.requestId=0;
  editing.awaiting=null;editing.autofit=null;$('autofit-result').hidden=true;
  feed.src='/frozen/'+editing.id+'.jpg';feed.hidden=false;$('empty').hidden=true;stream=false;canvas.hidden=false;
  viewport.focus();draw();
  log('info','Kalibrierung: erkannten Rahmen anklicken oder ✎ zum Verschieben/Ecken-ziehen, ✓ bestätigt. Danach folgt automatisch ein OCR-Vorschlag - ebenso mit ✎/✓ pruefen. Escape bricht die Bearbeitung ab.');
 }catch(e){log('error',e.message);}
}
function homography(q){
 const [p0,p1,p2,p3]=q,dx1=p1[0]-p2[0],dx2=p3[0]-p2[0],dx3=p0[0]-p1[0]+p2[0]-p3[0],dy1=p1[1]-p2[1],dy2=p3[1]-p2[1],dy3=p0[1]-p1[1]+p2[1]-p3[1],den=dx1*dy2-dx2*dy1;
 let g=0,h=0;if(Math.abs(den)>1e-12){g=(dx3*dy2-dx2*dy3)/den;h=(dx1*dy3-dx3*dy1)/den;}
 return [p1[0]-p0[0]+g*p1[0],p3[0]-p0[0]+h*p3[0],p0[0],p1[1]-p0[1]+g*p1[1],p3[1]-p0[1]+h*p3[1],p0[1],g,h,1];
}
function invert3(m){const [a,b,c,d,e,f,g,h,i]=m,A=e*i-f*h,B=c*h-b*i,C=b*f-c*e,D=f*g-d*i,E=a*i-c*g,F=c*d-a*f,G=d*h-e*g,H=b*g-a*h,I=a*e-b*d,det=a*A+b*D+c*G;if(Math.abs(det)<1e-12)return null;return [A,B,C,D,E,F,G,H,I].map(v=>v/det);}
function transform(m,x,y){const z=m[6]*x+m[7]*y+m[8];return [(m[0]*x+m[1]*y+m[2])/z,(m[3]*x+m[4]*y+m[5])/z];}
function project(u,v){return transform(homography(editing.quad),u,v);}
function unproject(x,y){const inverse=invert3(homography(editing.quad));return inverse?transform(inverse,x,y):[x,y];}
function ocrPoint(u,v){const [x,y,w,h]=editing.ocr_box;return project(x+u*w,y+v*h);}
function ocrCorners(){return [[0,0],[1,0],[1,1],[0,1]].map(([u,v])=>ocrPoint(u,v));}
function path(points,colour,width=1){ctx.strokeStyle=colour;ctx.lineWidth=width;ctx.beginPath();ctx.moveTo(points[0][0]*canvas.width,points[0][1]*canvas.height);for(let i=1;i<points.length;i++)ctx.lineTo(points[i][0]*canvas.width,points[i][1]*canvas.height);ctx.closePath();ctx.stroke();}
function gridBox(box,colour,width=1){const [x,y,w,h]=box;path([[x,y],[x+w,y],[x+w,y+h],[x,y+h]].map(([u,v])=>ocrPoint(u,v)),colour,width);}
function positionButtons(el,anchor,offsetX,offsetY,w,h){
 el.style.left=(offsetX+anchor[0]*w+6)+'px';
 el.style.top=(offsetY+anchor[1]*h-28)+'px';
}
function pointInQuad(pt,quad){
 // Punkt-in-Polygon (Ray-Casting), auch fuer rotierte Vierecke gueltig.
 let inside=false;
 for(let i=0,j=3;i<4;j=i++){
  const [xi,yi]=quad[i],[xj,yj]=quad[j];
  if((yi>pt[1])!==(yj>pt[1]) && pt[0]<(xj-xi)*(pt[1]-yi)/(yj-yi)+xi)inside=!inside;
 }
 return inside;
}
function draw(){
 if(!editing)return;
 const scale=Math.min(viewport.clientWidth/editing.width,viewport.clientHeight/editing.height);
 const w=Math.round(editing.width*scale),h=Math.round(editing.height*scale);
 canvas.width=w;canvas.height=h;canvas.style.width=w+'px';canvas.style.height=h+'px';
 const offsetX=(viewport.clientWidth-w)/2,offsetY=(viewport.clientHeight-h)/2;
 canvas.style.left=offsetX+'px';canvas.style.top=offsetY+'px';
 ctx.clearRect(0,0,w,h);
 const roiActive=editing.stage==='roi';
 // Kandidaten (nur Stufe A, Browse-Modus): duenn, anklickbar, keine Ecken.
 if(roiActive&&editing.mode==='browse')
  for(const [bx,by,bw,bh] of editing.candidates)path([[bx,by],[bx+bw,by],[bx+bw,by+bh],[bx,by+bh]],'rgba(166,214,166,.35)',1);
 // ROI-Rahmen: aktiv in Stufe A, sonst (Stufe B) inert, aber weiter
 // anklickbar (Klick darin fuehrt zurueck zu Stufe A).
 ctx.setLineDash(roiActive&&editing.pending?[6,4]:[]);
 path(editing.quad,roiActive?'#a6d6a6':'rgba(166,214,166,.55)',roiActive?2:1);
 ctx.setLineDash([]);
 if(roiActive&&editing.mode==='edit')
  for(let i=0;i<4;i++){ctx.fillStyle=i===editing.selected?'#ffffff':'#a6d6a6';ctx.fillRect(editing.quad[i][0]*w-5,editing.quad[i][1]*h-5,10,10);}
 // OCR-Raster/-Rahmen erst ab Stufe B sichtbar.
 if(!roiActive){
  for(const box of editing.ocr_grid.cells)gridBox(box,'rgba(240,208,128,.65)');
  if(editing.ocr_grid.sign)gridBox(editing.ocr_grid.sign,'rgba(240,208,128,.65)');
  for(const box of editing.ocr_grid.cells)for(const [,sx,sy] of editing.ocr_grid.samples){const p=ocrPoint(box[0]+sx*box[2],box[1]+sy*box[3]);ctx.fillStyle='rgba(240,208,128,.8)';ctx.beginPath();ctx.arc(p[0]*w,p[1]*h,1.6,0,2*Math.PI);ctx.fill();}
  if(editing.ocr_grid.decimal_after!==null){const box=editing.ocr_grid.cells[editing.ocr_grid.decimal_after],p=ocrPoint(box[0]+box[2],box[1]+.88*box[3]);ctx.strokeStyle='#7fdbe8';ctx.lineWidth=2;ctx.beginPath();ctx.arc(p[0]*w,p[1]*h,4,0,2*Math.PI);ctx.stroke();}
  const oc=ocrCorners();
  ctx.setLineDash(editing.pending?[6,4]:[]);
  path(oc,'#f0d080',2);
  ctx.setLineDash([]);
  if(editing.mode==='edit')
   for(let i=0;i<4;i++){ctx.fillStyle=i===editing.selected?'#ffffff':'#f0d080';ctx.fillRect(oc[i][0]*w-5,oc[i][1]*h-5,10,10);}
 }
 // TUI-Buttons: nur die aktive Stufe zeigt ihr Paar, direkt an der Box.
 $('roi-buttons').hidden=!roiActive;$('ocr-buttons').hidden=roiActive;
 if(roiActive)$('autofit-result').hidden=true; // nur in Stufe B relevant
 if(roiActive)positionButtons($('roi-buttons'),editing.quad[1],offsetX,offsetY,w,h);
 else positionButtons($('ocr-buttons'),ocrPoint(1,0),offsetX,offsetY,w,h);
 const pending=!!editing.pending;
 for(const id of ['roi-confirm','roi-toggle','ocr-confirm','ocr-calibrate','ocr-toggle'])$(id).disabled=pending;
 $('roi-toggle').textContent=(roiActive&&editing.mode==='edit')?'✕':'✎';
 $('ocr-toggle').textContent=(!roiActive&&editing.mode==='edit')?'✕':'✎';
}
function point(event){const box=canvas.getBoundingClientRect();return [(event.clientX-box.left)/box.width,(event.clientY-box.top)/box.height];}
function nearestHandle(x,y){
 // Nur die Ecken der jeweils aktiven Stufe - ROI und OCR sind nie
 // gleichzeitig interaktiv, die fruehere Ecken-Prioritaetslogik zwischen
 // beiden ist dadurch strukturell unnoetig geworden.
 const points=editing.stage==='roi'?editing.quad:ocrCorners();
 let best=null,distance=Infinity;
 for(let i=0;i<4;i++){const dx=(x-points[i][0])*canvas.width,dy=(y-points[i][1])*canvas.height,d=Math.hypot(dx,dy);if(d<distance){best=i;distance=d;}}
 return distance<=18?best:null;
}
function moveQuad(dx,dy){const q=editing.quad,minX=Math.min(...q.map(p=>p[0])),maxX=Math.max(...q.map(p=>p[0])),minY=Math.min(...q.map(p=>p[1])),maxY=Math.max(...q.map(p=>p[1]));dx=Math.max(-minX,Math.min(1-maxX,dx));dy=Math.max(-minY,Math.min(1-maxY,dy));editing.quad=q.map(([x,y])=>[x+dx,y+dy]);}
function moveOcr(dx,dy){const r=editing.ocr_box;dx=Math.max(-r[0],Math.min(1-r[0]-r[2],dx));dy=Math.max(-r[1],Math.min(1-r[1]-r[3],dy));editing.ocr_box=[r[0]+dx,r[1]+dy,r[2],r[3]];}
function setOcrCorner(index,u,v){const r=editing.ocr_box,left=r[0],top=r[1],right=left+r[2],bottom=top+r[3],gap=.01;u=Math.max(0,Math.min(1,u));v=Math.max(0,Math.min(1,v));const nl=index===0||index===3?Math.min(u,right-gap):left,nr=index===1||index===2?Math.max(u,left+gap):right,nt=index===0||index===1?Math.min(v,bottom-gap):top,nb=index===2||index===3?Math.max(v,top+gap):bottom;editing.ocr_box=[nl,nt,nr-nl,nb-nt];}
canvas.onpointerdown=event=>{
 // Waehrend eine Vermutung/Bestaetigung unterwegs ist, keine neue
 // Ziehbewegung beginnen - das war die Ursache des gemeldeten Bugs: eine
 // spaet eintreffende Vermutung wurde von einer zwischenzeitlichen
 // Ziehbewegung mit noch altem Zustand ueberschrieben.
 if(!editing||editing.pending)return;
 canvas.setPointerCapture(event.pointerId);
 const [x,y]=point(event);
 if(editing.stage==='roi'&&editing.mode==='browse'){
  const hit=editing.candidates.findIndex(([bx,by,bw,bh])=>x>=bx&&x<=bx+bw&&y>=by&&y<=by+bh);
  if(hit>=0){const [bx,by,bw,bh]=editing.candidates[hit];editing.quad=[[bx,by],[bx+bw,by],[bx+bw,by+bh],[bx,by+bh]];draw();}
  return;
 }
 if(editing.stage==='ocr'&&editing.mode==='browse'){
  // Zurueck zu Stufe A hebt einen evtl. vorhandenen Autofit-Vorschlag auf: er
  // wurde gegen die bisherige ROI/OCR-Geometrie gefittet und ist ungueltig,
  // sobald die ROI erneut zur Bearbeitung freigegeben wird (Review-Fund).
  if(pointInQuad([x,y],editing.quad)){
   editing.stage='roi';editing.mode='browse';editing.selected=null;
   if(editing.autofit){editing.autofit=null;updateAutofitResult(null);log('info','Autofit-Vorschlag verworfen: ROI wird erneut bearbeitet.');}
   draw();
  }
  return;
 }
 // Edit-Modus: Ecke ziehen oder Koerper verschieben.
 const corner=nearestHandle(x,y);editing.selected=corner;
 if(editing.stage==='roi')drag={target:'roi',start:[x,y],quad:editing.quad.map(p=>[...p]),corner};
 else drag={target:'ocr',start:[x,y],startUV:unproject(x,y),ocr:[...editing.ocr_box],corner};
 draw();
};
canvas.onpointermove=event=>{
 if(!drag)return;
 const [x,y]=point(event);
 if(drag.target==='roi'){editing.quad=drag.quad.map(p=>[...p]);if(drag.corner===null)moveQuad(x-drag.start[0],y-drag.start[1]);else editing.quad[drag.corner]=[Math.max(0,Math.min(1,x)),Math.max(0,Math.min(1,y))];}
 else{editing.ocr_box=[...drag.ocr];const uv=unproject(x,y);if(drag.corner===null)moveOcr(uv[0]-drag.startUV[0],uv[1]-drag.startUV[1]);else setOcrCorner(drag.corner,uv[0],uv[1]);}
 draw();
};
canvas.onpointerup=()=>{drag=null;};
canvas.onpointercancel=()=>{drag=null;draw();};
function unfreeze(){editing=null;drag=null;canvas.hidden=true;feed.removeAttribute('src');stream=false;$('ground-truth').hidden=true;$('autofit-result').hidden=true;poll();}
viewport.ondblclick=freeze;
viewport.onkeydown=async event=>{
 if(/^(INPUT|SELECT|TEXTAREA)$/.test(event.target.tagName))return;
 if(event.key==='e'&&!editing){event.preventDefault();await freeze();return;}
 if(!editing)return;
 if(event.key==='Escape'){event.preventDefault();unfreeze();return;}
};
function toggleEdit(stage){
 if(editing.pending)return;
 // Ecken-/Koerper-Ziehen (onpointermove) findet nur im Edit-Modus statt, der
 // ausschliesslich hier betreten wird - ein evtl. Autofit-Vorschlag war fuer
 // die bisherige Geometrie gefittet und darf weder beim Betreten (weitere
 // Ziehbewegungen aendern die Geometrie) noch beim Verwerfen (Rueckfall auf
 // preEdit ist ebenfalls eine Geometrieaenderung) weiter gueltig sein.
 if(editing.autofit){editing.autofit=null;updateAutofitResult(null);log('info','Autofit-Vorschlag verworfen: Geometrie wird bearbeitet.');}
 if(editing.mode==='edit'){
  if(stage==='roi')editing.quad=editing.preEdit;else editing.ocr_box=editing.preEdit;
  editing.mode='browse';
 }else{
  editing.preEdit=stage==='roi'?editing.quad.map(p=>[...p]):[...editing.ocr_box];
  editing.mode='edit';
 }
 editing.selected=null;draw();
}
async function confirmRoi(){
 if(editing.pending)return;
 editing.pending='ocr.suggest';const requestId=++editing.requestId;draw();
 try{
  const result=await command('ocr.suggest',{id:editing.id,quad:editing.quad});
  if(!editing||editing.requestId!==requestId)return; // ueberholt (Escape/erneuter Aufruf)
  if(result.ocr_box)editing.ocr_box=result.ocr_box;
  else log('warn','OCR-Vorschlag: kein Kandidat im markierten Bereich gefunden.');
  editing.stage='ocr';editing.mode='browse';editing.selected=null;
 }catch(e){log('error',e.message);}
 finally{if(editing)editing.pending=null;draw();}
}
async function sendRoiConfirm(extra){
 const requestId=editing.requestId+=1;
 try{
  await command('roi',{id:editing.id,quad:editing.quad,ocr_box:editing.ocr_box,role:state.config.role,...extra});
  if(!editing||editing.requestId!==requestId)return;
  unfreeze();
 }catch(e){log('error',e.message);if(editing){editing.pending=null;draw();}}
}
async function confirmOcr(){
 if(editing.pending)return;
 // Sperre VOR jedem await setzen (wie ueberall sonst in diesem Modul) - sonst
 // koennte ein zweiter Klick waehrend des layout.set_many-Sendens denselben
 // Uebernahmepfad ein zweites Mal anstossen, oder Escape zwischendurch
 // editing auf null setzen, waehrend dieser Aufruf noch darauf schreibt.
 editing.pending='roi';draw();
 // Autofit-Vorschlag ist bis hierher reine Vorschau (siehe runAutofit) - erst
 // der ✓-Klick uebernimmt sein Raster, und zwar VOR der roi-Bestaetigung:
 // roi prueft frame.revision gegen die aktuelle Revision, die layout.set_many
 // gerade erhoeht (siehe layout.set_many im Controller).
 if(editing.autofit){
  try{await command('layout.set_many',{values:editing.autofit.layout});}
  catch(e){log('error',e.message);if(editing){editing.pending=null;draw();}return;}
  if(!editing)return; // Escape waehrend des Sendens
 }
 if(state.mode==='annotate'){editing.awaiting='confirm';$('ground-truth').hidden=false;$('ground-truth-input').value='';$('ground-truth-input').focus();return;}
 await sendRoiConfirm({});
}
async function calibrate(){
 if(editing.pending)return;
 $('ground-truth').hidden=false;$('ground-truth-input').value='';$('ground-truth-input').focus();
 editing.awaiting='autofit';
}
function updateAutofitResult(r){
 const el=$('autofit-result');
 if(!r){el.hidden=true;return;}
 el.hidden=false;el.classList.toggle('flat',!!r.flat_optimum);
 el.textContent=`Autofit: liest ${r.preview.raw_text} · Trennschärfe ${r.separation}`+(r.flat_optimum?' · mehrdeutig, Raster prüfen':'');
}
async function runAutofit(text){
 editing.pending='layout.autofit';const requestId=++editing.requestId;draw();
 try{
  const r=await command('layout.autofit',{id:editing.id,quad:editing.quad,ocr_box:editing.ocr_box,text});
  if(!editing||editing.requestId!==requestId)return; // ueberholt (Escape/erneuter Aufruf)
  if(!r.matched){log('warn','Autofit: '+(r.reason||'kein passendes Raster gefunden'));editing.autofit=null;updateAutofitResult(null);return;}
  editing.autofit=r;editing.ocr_box=r.ocr_box; // nur Vorschau, uebernommen erst durch confirmOcr()
  if(r.flat_optimum)log('warn','Autofit: mehrere verschiedene Raster lesen diesen Wert gleich gut - Raster im Bild pruefen.');
  log('info',`Autofit: liest ${r.preview.raw_text}, Trennschärfe ${r.separation}`);
  updateAutofitResult(r);
 }catch(e){log('error',e.message);if(editing)editing.autofit=null;updateAutofitResult(null);}
 finally{if(editing)editing.pending=null;draw();}
}
$('roi-confirm').onclick=()=>confirmRoi();
$('roi-toggle').onclick=()=>toggleEdit('roi');
$('ocr-confirm').onclick=()=>confirmOcr();
$('ocr-calibrate').onclick=()=>calibrate();
$('ocr-toggle').onclick=()=>toggleEdit('ocr');
$('ground-truth-cancel').onclick=()=>{$('ground-truth').hidden=true;if(editing){editing.awaiting=null;editing.pending=null;draw();}viewport.focus();};
$('ground-truth-ok').onclick=async()=>{
 const text=$('ground-truth-input').value.trim();
 $('ground-truth').hidden=true;
 const awaiting=editing?editing.awaiting:null;if(editing)editing.awaiting=null;
 if(awaiting==='autofit'){await runAutofit(text);viewport.focus();return;}
 await sendRoiConfirm({ground_truth_text:text});
 viewport.focus();
};
$('ground-truth-input').onkeydown=event=>{
 if(event.key==='Enter'){event.preventDefault();$('ground-truth-ok').click();}
 if(event.key==='Escape'){event.preventDefault();$('ground-truth-cancel').click();}
};
/* Clipaufnahme: ein getipptes Label deckt den ganzen Clip ab, kein Bestaetigungsmechanismus. */
function updateClipPanel(clip){
 if(!clip)return;
 const recording=clip.state==='recording';
 $('clip-start').disabled=recording;
 $('clip-device').disabled=$('clip-text').disabled=$('clip-seconds').disabled=recording;
 $('clip-stop').disabled=!recording;
 $('clip-status').textContent=recording?`${clip.frames} Bilder · ${clip.dropped} verworfen · ${clip.seconds_left.toFixed(1)} s`:'';
}
$('clip-start').onclick=async()=>{
 const device_id=$('clip-device').value.trim();
 const ground_truth_text=$('clip-text').value.trim();
 const seconds=Number($('clip-seconds').value);
 try{await command('clip.start',{device_id,ground_truth_text,seconds});}
 catch(e){log('error',e.message);}
 await poll();
};
$('clip-stop').onclick=async()=>{
 try{await command('clip.stop');}
 catch(e){log('error',e.message);}
 await poll();
};
setInterval(()=>{if(!editing && (performance.now()-lastReply>2000||performance.now()-lastProgress>2000))disconnect();},250);
select('setup');
log('info','Einrichtung im setup-Tab: Werte auswählen, Tasten in Klammern lösen Aktionen aus. Kamerabereich mit E oder Doppelklick bearbeiten.');
setInterval(poll,500);poll();
