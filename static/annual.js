const stage=document.querySelector('#annual-stage');
const canvas=document.querySelector('#annual-canvas');
const ctx=canvas.getContext('2d');
const yearSelect=document.querySelector('#annual-year');
const status=document.querySelector('#annual-status');
const tooltip=document.querySelector('#annual-tooltip');
const tracePanel=document.querySelector('.annual-details');
const traceTitle=document.querySelector('#annual-detail-title');
const traceBack=document.querySelector('#annual-trace-close');
const pause=document.querySelector('#pause');
const motion=matchMedia('(prefers-reduced-motion: reduce)');
const positions={production:.16,imports:.88,refining:.27,electricity:.40,cooking:.53,industry:.66,transport:.79,other:.92,co2:.13};
const icons={production:'▥',imports:'⇢',refining:'▥',electricity:'ϟ',cooking:'⌂',industry:'▥',transport:'⇢',other:'◇',co2:'CO₂'};
const nf=new Intl.NumberFormat('en-US',{maximumFractionDigits:2});
const exact=new Intl.NumberFormat('en-US',{maximumFractionDigits:8});
const activities={'ELECTRICITY':'ผลิตไฟฟ้า','ELECTRICITY (EGAT)':'ผลิตไฟฟ้า · กฟผ.','ELECTRICITY (IPP)':'ผลิตไฟฟ้า · IPP','ELECTRICITY (SPP)':'ผลิตไฟฟ้า · SPP','INDUSTRY':'อุตสาหกรรม','COOKING':'หุงต้ม','NGV':'รถยนต์ NGV','AUTOMOBILE':'รถยนต์ LPG','GSP':'โรงแยกก๊าซ','FEEDSTOCK':'วัตถุดิบป้อนกระบวนการ','OWN USED ENERGY':'ใช้เป็นพลังงานในกิจการ','OWN USED FEEDSTOCK':'ใช้เป็นวัตถุดิบในกิจการ','ELECTRICITY GENERATION':'ผลิตไฟฟ้า','OTHER ECONOMIC SECTORS':'เศรษฐกิจอื่น','TRANSPORT':'ขนส่ง'};
let fuel='all',data=null,selected=null,controller=null;
let traced=null;
let paused=motion.matches,frame=null,time=0,previous=0;
function paragraph(text,cls){const p=document.createElement('p');p.textContent=text;if(cls)p.className=cls;return p;}
function summary(node){
 if(['co2','production','imports'].includes(node.id)){
  const totals=new Map();
  for(const row of node.records){
   const label=row.source_code+' · '+row.product+' · '+row.unit;
   totals.set(label,(totals.get(label)||0)+Number(row.amount));
  }
  return [...totals].map(([key,value])=>key+' · '+nf.format(value)).join('\n');
 }
 return node.summaries.map(x=>nf.format(Number(x.amount))+' '+x.unit).join(' · ');
}
function hideHover(){
 tooltip.hidden=true;selected=null;
 for(const el of document.querySelectorAll('.annual-node'))el.classList.remove('selected');
}
function showHover(node){
 selected=node.id;
 for(const el of document.querySelectorAll('.annual-node'))el.classList.toggle('selected',el.dataset.node===selected);
 tooltip.replaceChildren();
 const heading=document.createElement('strong');heading.textContent=node.label+' · '+data.year;tooltip.append(heading);
 const lines=document.createElement('div');lines.className='annual-hover-lines';
 for(const line of (summary(node)||'ไม่พบข้อมูล').split('\n'))lines.append(paragraph(line));
 tooltip.append(lines,paragraph(node.complete?'ครบ 12 เดือน':'รวมเฉพาะเดือนที่มีข้อมูล'));
 if(!['production','imports','co2'].includes(node.id))tooltip.append(paragraph([...new Set(node.records.map(r=>r.source_code))].join(' · ')));
 tooltip.hidden=false;
}
function closeTrace(restoreFocus=false){
 const previous=traced;
 traced=null;
 tracePanel.hidden=true;
 stage.classList.remove('tracing');
 for(const el of stage.querySelectorAll('.trace-input'))el.classList.remove('trace-input');
 for(const button of stage.querySelectorAll('[aria-controls="annual-trace"]'))button.setAttribute('aria-expanded','false');
 if(restoreFocus&&previous)stage.querySelector(`[data-node="${previous.id}"]`)?.focus();
 paint();
}
function openTrace(node){
 if(traced?.id===node.id){closeTrace(true);return;}
 closeTrace();hideHover();traced=node;
 stage.classList.add('tracing');
 stage.querySelector(`[data-node="${node.id}"]`).setAttribute('aria-expanded','true');
 if(node.id!=='co2')for(const group of new Set(node.records.map(row=>row.fuel_group).filter(Boolean)))stage.querySelector(`.fuel-${group}`)?.classList.add('trace-input');
 renderTrace(node);
 tracePanel.hidden=false;
 traceTitle.focus({preventScroll:true});
 tracePanel.scrollIntoView({block:'nearest'});
 paint();
}
function renderTrace(node){
 const {id}=node;
 const box=document.querySelector('#annual-evidence');box.replaceChildren();if(!data)return;
 traceTitle.textContent=`${node.label} → ${id==='co2'?'หลักฐานการปล่อย':'เชื้อเพลิงที่ใช้ (Input)'} · ปี ${data.year}`;
 document.querySelector('#annual-coverage').textContent=node.records.length ? (node.complete?'ทุกรายการมีข้อมูลครบ 12 เดือน':'รวมเฉพาะเดือนที่มีข้อมูล') : 'ยังไม่มีข้อมูล';
 let note='แสดงปริมาณตามกิจกรรมและแหล่งข้อมูล หน่วยแต่ละชนิดแยกยอดจากกัน';
 if(id==='production'||id==='imports')note='แยกชุดข้อมูลตามแหล่ง ผลิตภัณฑ์ และหน่วย อัตรารายวันคูณวันจริงของแต่ละเดือน ชุดข้อมูลมีขอบเขตต่างกัน';
 if(id==='cooking')note='ต้นทาง SRC-09 ระบุ COOKING หรือการหุงต้ม ยังไม่มีตัวแยกครัวเรือนออกจากร้านค้าและกิจกรรมหุงต้มอื่น';
 if(id==='co2')note='SRC-18 ถึง SRC-21 รายงาน CO₂ แยกตามสาขาและชนิดเชื้อเพลิง แต่ไม่มีรหัสเชื่อมกับรายการ Input โดยตรง ด้านล่างคือหลักฐานการปล่อยที่ตรวจย้อนกลับได้';
 if(id==='electricity')note='ปริมาณเชื้อเพลิงที่ใช้ผลิตไฟฟ้า อ้าง SRC-15 สำหรับถ่านหิน SRC-11 สำหรับก๊าซ และ SRC-22 สำหรับน้ำมัน ยังไม่มีปริมาณไฟฟ้าที่ผลิตเป็น kWh';
 if(id==='refining')note='ปริมาณน้ำมันดิบเข้าโรงกลั่น SRC-04 อัตรารายเดือน BBL/DAY คูณจำนวนวันของเดือนก่อนรวมเป็น BBL ในปีที่เลือก';
 document.querySelector('#annual-detail-note').textContent=note;
 if(id!=='co2')box.append(traceDiagram(node));
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
function traceDiagram(node){
 const diagram=document.createElement('div');
 diagram.className='trace-diagram';
 function step(title,lines){
  const card=document.createElement('section');
  const heading=document.createElement('h4');
  heading.textContent=title;
  card.append(heading,...lines.map(line=>paragraph(line)));
  diagram.append(card);
 }
 step('Output · กิจกรรมที่เลือก',[node.label+' · '+data.year]);
 const products=[...new Set(node.records.map(row=>row.product))];
 step('ย้อนดู Input',products.length?products:['ไม่มีรายการเชื้อเพลิงตามตัวกรอง']);
 // เทียบเฉพาะสาขาและกลุ่มเชื้อเพลิงที่ระบุตรงกัน ยอด CO₂ เป็นของทั้งสาขา
 const sectorSource={electricity:'SRC-21',industry:'SRC-19',transport:'SRC-20'}[node.id];
 const emissionProduct={coal:'CO2 - COAL / LIGNITE',gas:'CO2 - NATURAL GAS',oil:'CO2 - OIL'};
 const observed=new Set(node.records.map(row=>emissionProduct[row.fuel_group]).filter(Boolean));
 const emissions=(data.nodes.find(item=>item.id==='co2')?.records||[])
  .filter(row=>row.source_code===sectorSource&&observed.has(row.product));
 step('CO₂ ที่รายงานทั้งสาขา',emissions.length
  ? emissions.map(row=>row.product+' · '+nf.format(Number(row.amount))+' '+row.unit+' · '+row.source_code+' · '+row.months.length+'/12 เดือน')
  : ['ไม่มีหลักฐาน CO₂ ที่จับคู่กับสาขาและเชื้อเพลิงตามตัวกรองนี้']);
 if(emissions.length)diagram.lastElementChild.append(paragraph('ยอดระดับสาขา ยังระบุส่วนของแต่ละ Input ไม่ได้'));
 return diagram;
}
function renderNodes(){
 const container=document.querySelector('#annual-nodes');container.replaceChildren();
 for(const node of data.nodes){
  const button=document.createElement('button');button.className='annual-node '+node.id+(node.records.length?'':' empty');button.type='button';button.dataset.node=node.id;button.style.top=(positions[node.id]*100)+'%';
  const icon=document.createElement('span');icon.className='iso-block';icon.textContent=icons[node.id];icon.setAttribute('aria-hidden','true');
  const text=document.createElement('span');const label=document.createElement('span');label.className='node-label';label.textContent=node.label;
  const amount=document.createElement('span');amount.className='node-quantity';amount.textContent=node.records.length?(['co2','production','imports'].includes(node.id)?'ชี้เพื่อดูปริมาณแยกแหล่ง':node.summaries.map(x=>`${nf.format(Number(x.amount))} ${x.unit}`).join('\n')):'ไม่มีข้อมูลตามเงื่อนไข';
  const coverage=document.createElement('span');coverage.className='node-completeness';coverage.textContent=node.records.length?(node.complete?'ครบ 12 เดือน':'บางรายการมีข้อมูลไม่ครบปี'):'';
  text.append(label,amount,coverage);button.append(icon,text);
  button.setAttribute('aria-describedby','annual-tooltip');
  button.addEventListener('mouseenter',()=>showHover(node));
  button.addEventListener('mouseleave',hideHover);
  button.addEventListener('focus',()=>{if(button.matches(':focus-visible'))showHover(node);});
  button.addEventListener('blur',hideHover);
  if(!['production','imports'].includes(node.id)){
   button.setAttribute('aria-controls','annual-trace');
   button.setAttribute('aria-expanded','false');
   button.addEventListener('click',()=>openTrace(node));
  }else button.addEventListener('click',event=>{if(event.pointerType==='touch'){if(selected===node.id)hideHover();else showHover(node);}});
  container.append(button);
 }
 hideHover();paint();
}
async function load(year){
 closeTrace();
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
 const tracedFuels=new Set(traced?.id==='co2'?[]:traced?.records.map(row=>row.fuel_group));
 for(const [kind,y]of [['coal',.32],['gas',.52],['oil',.72]])paths.push({path:[w*.28,h*y,w*.33,h*y,w*.34,h*.52,w*.37,h*.52],color:kind==='oil'?'#c9b476':kind==='gas'?'#82c8dc':'#7fd7ac',available:fuel==='all'||fuel===kind,highlight:tracedFuels.has(kind)});
 for(const [id,y] of Object.entries(positions)){
  const available=!!data?.nodes.find(n=>n.id===id)?.records.length;
  const path=['production','imports'].includes(id)?[w*.28,h*y,w*.33,h*y,w*.34,h*.52,w*.37,h*.52]:id==='co2'?[w*.44,h*.44,w*.44,h*.25,w*.43,h*.13,w*.40,h*.13]:[w*.48,h*.52,w*.60,h*.52,w*.61,h*y,w*.72,h*y];
  paths.push({path,color:id==='co2'?'#e2aa82':'#9cc596',available,highlight:id!=='co2'&&traced?.id===id});
 }
 for(const {path,color,available,highlight} of paths){if(!available || !data)continue;ctx.beginPath();curve(path);ctx.strokeStyle=color+(highlight?'ff':traced?'30':'77');ctx.lineWidth=highlight?3:2;ctx.setLineDash([4,6]);ctx.stroke();ctx.setLineDash([]);
  if(traced&&!highlight)continue;
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

traceBack.addEventListener('click',()=>closeTrace(true));
stage.addEventListener('mouseleave',hideHover);
document.addEventListener('keydown',event=>{if(event.key==='Escape'){hideHover();if(traced)closeTrace(true);}});
document.addEventListener('pointerdown',event=>{if(!event.target.closest('.annual-node'))hideHover();});
