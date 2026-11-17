const stage=document.querySelector('#annual-stage');
const canvas=document.querySelector('#annual-canvas');
const ctx=canvas.getContext('2d');
const yearSelect=document.querySelector('#annual-year');
const status=document.querySelector('#annual-status');
const tooltip=document.querySelector('#annual-tooltip');
const pause=document.querySelector('#pause');
const motion=matchMedia('(prefers-reduced-motion: reduce)');
const positions={refining:.27,electricity:.40,cooking:.53,industry:.66,transport:.79,other:.92,co2:.13};
const icons={refining:'▥',electricity:'ϟ',cooking:'⌂',industry:'▥',transport:'⇢',other:'◇',co2:'CO₂'};
const nf=new Intl.NumberFormat('en-US',{maximumFractionDigits:2});
const exact=new Intl.NumberFormat('en-US',{maximumFractionDigits:8});
const activities={'ELECTRICITY':'ผลิตไฟฟ้า','ELECTRICITY (EGAT)':'ผลิตไฟฟ้า · กฟผ.','ELECTRICITY (IPP)':'ผลิตไฟฟ้า · IPP','ELECTRICITY (SPP)':'ผลิตไฟฟ้า · SPP','INDUSTRY':'อุตสาหกรรม','COOKING':'หุงต้ม','NGV':'รถยนต์ NGV','AUTOMOBILE':'รถยนต์ LPG','GSP':'โรงแยกก๊าซ','FEEDSTOCK':'วัตถุดิบป้อนกระบวนการ','OWN USED ENERGY':'ใช้เป็นพลังงานในกิจการ','OWN USED FEEDSTOCK':'ใช้เป็นวัตถุดิบในกิจการ','ELECTRICITY GENERATION':'ผลิตไฟฟ้า','OTHER ECONOMIC SECTORS':'เศรษฐกิจอื่น','TRANSPORT':'ขนส่ง'};
let fuel='all',data=null,selected='electricity',controller=null;
let paused=motion.matches,frame=null,time=0,previous=0;
function paragraph(text,cls){const p=document.createElement('p');p.textContent=text;if(cls)p.className=cls;return p;}
function summary(node){if(node.id==="co2" && node.records.length) return "ดู CO₂ แยกตามสาขาและเชื้อเพลิง";return node.summaries.map(x=>`${nf.format(Number(x.amount))} ${x.unit}`).join(' · ');}
function selectNode(id){
 selected=id;
 for(const el of document.querySelectorAll('.annual-node'))el.classList.toggle('selected',el.dataset.node===id);
 const box=document.querySelector('#annual-evidence');box.replaceChildren();if(!data)return;
 const node=data.nodes.find(n=>n.id===id);
 document.querySelector('#annual-detail-title').textContent=`${node.label} · ปี ${data.year}`;
 document.querySelector('#annual-coverage').textContent=node.records.length ? (node.complete?'ทุกรายการมีข้อมูลครบ 12 เดือน':'รวมเฉพาะเดือนที่มีข้อมูล') : 'ยังไม่มีข้อมูล';
 let note='แสดงปริมาณตามกิจกรรมและแหล่งข้อมูล หน่วยแต่ละชนิดแยกยอดจากกัน';
 if(id==='cooking')note='ต้นทาง SRC-09 ระบุ COOKING หรือการหุงต้ม ยังไม่มีตัวแยกครัวเรือนออกจากร้านค้าและกิจกรรมหุงต้มอื่น';
 if(id==='co2')note='ผลรวม CO₂ ที่รายงานแยกตามเชื้อเพลิงและสาขา จาก SRC-18 ถึง SRC-21 ค่านี้เป็นข้อมูลการปล่อยที่รายงานแยกชุดจากปริมาณการใช้เชื้อเพลิง';
 if(id==='electricity')note='ปริมาณเชื้อเพลิงที่ใช้ผลิตไฟฟ้า อ้าง SRC-15 สำหรับถ่านหิน SRC-11 สำหรับก๊าซ และ SRC-22 สำหรับน้ำมัน ยังไม่มีปริมาณไฟฟ้าที่ผลิตเป็น kWh';
 if(id==='refining')note='ปริมาณน้ำมันดิบเข้าโรงกลั่น SRC-04 อัตรารายเดือน BBL/DAY คูณจำนวนวันของเดือนก่อนรวมเป็น BBL ในปีที่เลือก';
 document.querySelector('#annual-detail-note').textContent=note;
 if(!node.records.length){box.append(paragraph('ไม่พบปริมาณที่ระบุสาขานี้สำหรับเชื้อเพลิงและปีที่เลือก','annual-empty'));return;}
 const grid=document.createElement('div');grid.className='annual-grid';
 for(const row of node.records){
  const card=document.createElement('article');card.className='annual-evidence';
  const heading=document.createElement('h4');heading.textContent=activities[row.process]||row.process;
  const product=paragraph(row.product,'product');
  const amount=document.createElement('strong');amount.textContent=exact.format(Number(row.amount))+' ';
  const unit=document.createElement('small');unit.textContent=row.unit;amount.append(unit);
  const coverage=paragraph(row.complete?'ครบ 12 เดือน':'รวม '+row.months.length+'/12 เดือน · ขาดเดือน '+row.missing_months.join(', '));
  const calculation=paragraph(row.conversion==='monthly_rate_times_calendar_days'?'คำนวณจากอัตรา '+row.source_unit+' × วันของแต่ละเดือน':row.conversion==='thousand_tons_to_tons'?'แปลงจากพันตันเป็นตัน แล้วรวมเดือนที่มีข้อมูล':'รวมค่าของเดือนที่มีข้อมูล');
  const ref=paragraph(`${row.source_code} · Exchange ${row.exchange_ids.join(', ')}`);
  card.append(heading,product,amount,coverage,calculation,ref);grid.append(card);
 }
 box.append(grid);
}
function renderNodes(){
 const container=document.querySelector('#annual-nodes');container.replaceChildren();
 for(const node of data.nodes){
  const button=document.createElement('button');button.className='annual-node '+node.id+(node.records.length?'':' empty');button.type='button';button.dataset.node=node.id;button.style.top=(positions[node.id]*100)+'%';
  const icon=document.createElement('span');icon.className='iso-block';icon.textContent=icons[node.id];icon.setAttribute('aria-hidden','true');
  const text=document.createElement('span');const label=document.createElement('span');label.className='node-label';label.textContent=node.label;
  const amount=document.createElement('span');amount.className='node-quantity';amount.textContent=node.records.length?(node.id==='co2'?summary(node):node.summaries.map(x=>`${nf.format(Number(x.amount))} ${x.unit}`).join('\n')):'ไม่มีข้อมูลตามเงื่อนไข';
  const coverage=document.createElement('span');coverage.className='node-completeness';coverage.textContent=node.records.length?(node.complete?'ครบ 12 เดือน':'บางรายการมีข้อมูลไม่ครบปี'):'';
  text.append(label,amount,coverage);button.append(icon,text);
  function activate(){selectNode(node.id);}
  button.addEventListener('click',activate);button.addEventListener('focus',activate);
  button.addEventListener('mouseenter',()=>{activate();tooltip.textContent=node.label+' · '+data.year+'\n'+(summary(node)||'ไม่พบข้อมูล')+'\n'+(node.complete?'ครบ 12 เดือน':'ดูช่วงที่มีข้อมูลในรายละเอียดด้านล่าง');tooltip.hidden=false;});
  button.addEventListener('mouseleave',()=>tooltip.hidden=true);
  container.append(button);
 }
 selectNode(selected);paint();
}
async function load(year){
 if(controller)controller.abort();controller=new AbortController();const active=controller;
 status.textContent='กำลังรวมข้อมูลรายปี';data=null;tooltip.hidden=true;
 document.querySelector('#annual-nodes').replaceChildren();document.querySelector('#annual-evidence').replaceChildren();paint();
 try{
  const params=new URLSearchParams({fuel});if(year && /^\d{4}$/.test(String(year)))params.set('year',year);
  const response=await fetch('/api/annual-flow?'+params,{signal:active.signal});if(!response.ok)throw Error();
  data=await response.json();
  yearSelect.replaceChildren(...data.years.map(y=>new Option(y,y)));yearSelect.value=data.year;
  status.textContent=data.nodes.some(n=>n.records.length&&!n.complete)?'ปี '+data.year+' · บางชุดข้อมูลยังไม่ครบ 12 เดือน':'ปี '+data.year+' · ปริมาณจากฐานข้อมูล';
  for(const [kind,cls] of [['coal','fuel-coal'],['gas','fuel-gas'],['oil','fuel-oil']])document.querySelector('.'+cls).classList.toggle('fuel-inactive',fuel!=='all'&&fuel!==kind);
  renderNodes();
 }catch(e){if(e.name==='AbortError')return;status.textContent='อ่านข้อมูลไม่ได้ กรุณาเลือกปีหรือเชื้อเพลิงอีกครั้ง';document.querySelector('#annual-evidence').append(paragraph('ยังอ่านปริมาณรายปีไม่ได้','annual-empty'));}
}
function curve(path){ctx.moveTo(path[0],path[1]);ctx.bezierCurveTo(...path.slice(2));}
function point(t,p){const u=1-t;return [u*u*u*p[0]+3*u*u*t*p[2]+3*u*t*t*p[4]+t*t*t*p[6],u*u*u*p[1]+3*u*u*t*p[3]+3*u*t*t*p[5]+t*t*t*p[7]];}
function paint(){
 const w=stage.clientWidth,h=stage.clientHeight;ctx.clearRect(0,0,w,h);
 const paths=[];
 for(const [kind,y]of [['coal',.32],['gas',.52],['oil',.72]])paths.push({path:[w*.28,h*y,w*.33,h*y,w*.34,h*.52,w*.37,h*.52],color:kind==='oil'?'#c9b476':kind==='gas'?'#82c8dc':'#7fd7ac',available:fuel==='all'||fuel===kind});
 for(const [id,y] of Object.entries(positions)){
  const available=!!data?.nodes.find(n=>n.id===id)?.records.length;
  const path=id==='co2'?[w*.44,h*.44,w*.44,h*.25,w*.43,h*.13,w*.40,h*.13]:[w*.48,h*.52,w*.60,h*.52,w*.61,h*y,w*.72,h*y];
  paths.push({path,color:id==='co2'?'#e2aa82':'#9cc596',available});
 }
 for(const {path,color,available} of paths){if(!available || !data)continue;ctx.beginPath();curve(path);ctx.strokeStyle=available?color+'77':'#45616b55';ctx.lineWidth=available?2:1;ctx.setLineDash([4,6]);ctx.stroke();ctx.setLineDash([]);if(!available)continue;
  for(let i=0;i<9;i++){const t=(time*.09+i/9)%1,[x,y]=point(t,path);ctx.beginPath();ctx.arc(x,y,2.5,0,Math.PI*2);ctx.fillStyle=color;ctx.shadowColor=color;ctx.shadowBlur=7;ctx.fill();ctx.shadowBlur=0;}
 }
}
function tick(now){if(previous)time+=Math.min((now-previous)/1000,.1);previous=now;paint();frame=paused||document.hidden?null:requestAnimationFrame(tick);}
function sync(){if(frame)cancelAnimationFrame(frame);frame=null;previous=0;pause.textContent=paused?'เล่นภาพ':'หยุดภาพ';pause.setAttribute('aria-pressed',String(paused));paint();if(!paused&&!document.hidden)frame=requestAnimationFrame(tick);}
pause.addEventListener('click',()=>{paused=!paused;sync();});motion.addEventListener('change',()=>{paused=motion.matches;sync();});document.addEventListener('visibilitychange',sync);
new ResizeObserver(()=>{const r=Math.min(devicePixelRatio||1,2);canvas.width=stage.clientWidth*r;canvas.height=stage.clientHeight*r;ctx.setTransform(r,0,0,r,0,0);paint();}).observe(stage);
yearSelect.addEventListener('change',()=>load(yearSelect.value));for(const button of document.querySelectorAll('[data-fuel]'))button.addEventListener('click',()=>{fuel=button.dataset.fuel;for(const item of document.querySelectorAll('[data-fuel]'))item.setAttribute('aria-pressed',String(item===button));load(yearSelect.value);});
sync();load();
(async()=>{try{const r=await fetch('/api/overview');if(!r.ok)throw Error();const d=await r.json();document.querySelector('#exchanges').textContent=nf.format(d.exchanges);document.querySelector('#sources').textContent=nf.format(d.sources);document.querySelector('#period').textContent=`${d.first_year}–${d.last_year}`;document.querySelector('#health').textContent='● ข้อมูลจากฐานปัจจุบัน';}catch{document.querySelector('#health').textContent='อ่านภาพรวมไม่ได้';}})();
