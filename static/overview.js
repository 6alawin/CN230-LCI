const canvas = document.querySelector('#flow');
const stage = document.querySelector('#stage');
const context = canvas.getContext('2d');
const motion = matchMedia('(prefers-reduced-motion: reduce)');
const pause = document.querySelector('#pause');
let paused = motion.matches;
let frame = null;
let time = 0;
let previous = 0;
const fuels = {coal:['ถ่านหิน','◆'], gas:['ก๊าซธรรมชาติ','◌'], oil:['น้ำมัน','◒']};
function position(x, path) {
  const t = x;
  const u = 1 - t;
  return [u*u*u*path[0]+3*u*u*t*path[2]+3*u*t*t*path[4]+t*t*t*path[6],
          u*u*u*path[1]+3*u*u*t*path[3]+3*u*t*t*path[5]+t*t*t*path[7]];
}
function paint() {
  const w = stage.clientWidth, h = stage.clientHeight;
  context.clearRect(0,0,w,h);
  const small = w < 600;
  const left = w*(small ? .15 : .13), right = w*(small ? .85 : .86);
  const paths = [
    [[left+32,h*.5,w*.3,h*.5,w*.36,h*.5,w*.5-55,h*.5],'#7ae5bd'],
    [[w*.5+55,h*.5,w*.68,h*.5,w*.65,h*.25,right-32,h*.25],'#7ae5bd'],
    [[w*.5+55,h*.5,w*.68,h*.5,w*.65,h*.78,right-32,h*.78],'#e6a781']
  ];
  for (const [path,color] of paths) {
    context.beginPath(); context.moveTo(path[0],path[1]);
    context.bezierCurveTo(...path.slice(2)); context.strokeStyle=color+'45'; context.lineWidth=2; context.stroke();
    for(let i=0;i<5;i++) {
      const t = (time*.16+i/5)%1;
      const [x,y] = position(t,path);
      context.beginPath(); context.arc(x,y,3,0,Math.PI*2);
      context.fillStyle=color; context.shadowBlur=10; context.shadowColor=color; context.fill(); context.shadowBlur=0;
    }
  }
}
function tick(now) {
  if (previous) time += Math.min((now-previous)/1000,.1);
  previous=now; paint();
  frame = paused || document.hidden ? null : requestAnimationFrame(tick);
}
function syncMotion() {
  if(frame) cancelAnimationFrame(frame);
  frame=null;previous=0;
  pause.textContent=paused?'เล่นภาพ':'หยุดภาพ';pause.setAttribute('aria-pressed',String(paused));
  paint();
  if(!paused && !document.hidden) frame=requestAnimationFrame(tick);
}
pause.addEventListener('click',()=>{paused=!paused;syncMotion();});
motion.addEventListener('change',()=>{paused=motion.matches;syncMotion();});
document.addEventListener('visibilitychange',syncMotion);
new ResizeObserver(()=>{
  const ratio = Math.min(devicePixelRatio || 1,2);
  canvas.width=stage.clientWidth*ratio;canvas.height=stage.clientHeight*ratio;
  context.setTransform(ratio,0,0,ratio,0,0);paint();
}).observe(stage);
for(const button of document.querySelectorAll('[data-fuel]')) {
  button.addEventListener('click',()=>{
    for(const item of document.querySelectorAll('[data-fuel]')) item.setAttribute('aria-pressed',String(item===button));
    const [name,icon]=fuels[button.dataset.fuel];
    document.querySelector('#fuel-name').textContent=name;document.querySelector('#fuel-icon').textContent=icon;
    selectedFuel=button.dataset.fuel; loadFlow();
  });
}
syncMotion();
(async()=>{
  const health=document.querySelector('#health');
  try {
    const response=await fetch('/api/overview');if(!response.ok) throw new Error();
    const data=await response.json();
    const number = new Intl.NumberFormat('en-US');
    document.querySelector('#exchanges').textContent=number.format(data.exchanges);
    document.querySelector('#sources').textContent=number.format(data.sources);
    document.querySelector('#period').textContent=data.first_year == null ? '—' : `${data.first_year}–${data.last_year}`;
    health.textContent='● ข้อมูลจากฐานปัจจุบัน';
  } catch {health.textContent='อ่านภาพรวมไม่ได้ · ลองโหลดหน้าใหม่';}
})();

let selectedFuel='coal';
let selectedDetail='uses';
let flowData=null;
let flowController=null;
const periodSelect=document.querySelector('#flow-period');
const tooltip=document.querySelector('#flow-tooltip');
const numberFormat=new Intl.NumberFormat('en-US',{maximumFractionDigits:8});
const labels={uses:'นำเชื้อเพลิงไปใช้ทำอะไร',outputs:'ผลผลิตและการส่งออกที่รายงาน',emissions:'การปล่อย CO₂ แยกสาขา'};
const notes={
 uses:'ปริมาณตามกิจกรรมในเดือนที่เลือก แสดงหน่วยต้นทางแยกกัน โดยอ้างอิง SRC-15 สำหรับถ่านหิน SRC-11 สำหรับก๊าซ และ SRC-08 / SRC-22 สำหรับน้ำมัน',
 outputs:'แสดงรายการ OUT ของการผลิต การส่งออก หรือการกระจาย ในกลุ่มเชื้อเพลิงและเดือนเดียวกัน ข้อมูลสถิติแต่ละชุดมีขอบเขตต่างกัน จึงยังติดตามว่าเป็นผลผลิตจาก Input รายการใดโดยตรงไม่ได้',
 emissions:'CO₂ จากชุดข้อมูลการปล่อยตามชนิดเชื้อเพลิงและสาขาในเดือนเดียวกัน ไม่ได้คำนวณจากปริมาณเชื้อเพลิงด้านซ้าย'
};
const activityNames={
 'ELECTRICITY':'ผลิตไฟฟ้า','ELECTRICITY (EGAT)':'ผลิตไฟฟ้า · กฟผ.',
 'ELECTRICITY (IPP)':'ผลิตไฟฟ้า · IPP','ELECTRICITY (SPP)':'ผลิตไฟฟ้า · SPP',
 'ELECTRICITY GENERATION':'ผลิตไฟฟ้า','INDUSTRY':'อุตสาหกรรม',
 'NGV':'เชื้อเพลิงรถยนต์ NGV','GSP':'โรงแยกก๊าซ',
 'NATIONAL':'ภาพรวมประเทศ','TRANSPORT':'ขนส่ง','OTHER ECONOMIC SECTORS':'สาขาเศรษฐกิจอื่น'
};
const kindNames={PRODUCTION:'การผลิต',EXPORT:'ส่งออก',DISTRIBUTION:'กระจายผลิตภัณฑ์'};
function rowText(row) {
 return `${activityNames[row.process] || row.process} · ${row.product} · ${numberFormat.format(Number(row.amount))} ${row.unit} [${row.source_code} / exchange ${row.entity_id}]`;
}
function showDetail(category) {
 selectedDetail=category;
 for(const button of document.querySelectorAll('[data-tab]'))button.setAttribute('aria-pressed',String(button.dataset.tab===category));
 document.querySelector('#detail-title').textContent=labels[category];
 document.querySelector('#detail-note').textContent=notes[category];
 const container=document.querySelector('#detail-rows');container.replaceChildren();
 if(!flowData) {container.textContent='กำลังอ่านข้อมูล';return;}
 const rows=flowData[category];
 if(!rows.length) {
  const empty=document.createElement('div');empty.className='data-empty';empty.textContent='ไม่พบรายการตามชนิดเชื้อเพลิงและเดือนที่เลือก';container.append(empty);
 } else {
  const grid=document.createElement('div');grid.className='evidence-grid';
  for(const row of rows) {
   const item=document.createElement('article');item.className='evidence';
   const activity=document.createElement('div');activity.className='evidence-activity';activity.textContent=(kindNames[row.process_type] ? kindNames[row.process_type]+' · ' : '')+(activityNames[row.process] || row.process);
   const product=document.createElement('div');product.className='evidence-product';product.textContent=row.product;
   const amount=document.createElement('strong');amount.textContent=numberFormat.format(Number(row.amount))+' ';
   const unit=document.createElement('span');unit.textContent=row.unit;amount.append(unit);
   const ref=document.createElement('a');ref.href='/search?'+new URLSearchParams({q:row.source_code+' '+row.product+' ปี '+flowData.year});ref.textContent=`${row.source_code} / exchange ${row.entity_id} · ${flowData.year}-${String(flowData.month).padStart(2,'0')}`;
   item.append(activity,product,amount,ref);grid.append(item);
  }
  container.append(grid);
 }
 if(category==='outputs') {
  const warning=document.createElement('div');warning.className='output-warning';
  warning.textContent='ฐานชุดนี้ยังไม่มีปริมาณไฟฟ้าที่ผลิตเป็น kWh และไม่มีเส้นทางส่งต่อไฟฟ้าไปยังผู้ใช้ปลายทาง การตรวจว่าผลผลิตแต่ละรายการถูกนำไปใช้ต่อที่ใดจึงทำได้เท่าที่ข้อมูลแต่ละ Source ระบุ';container.append(warning);
 }
}
async function loadFlow(period) {
 if(flowController)flowController.abort();flowController=new AbortController();
 const controller=flowController;
 flowData=null;tooltip.hidden=true;showDetail(selectedDetail);
 document.querySelector('#flow-status').textContent='กำลังอ่านข้อมูลจริง';
 document.querySelector('#input-quantity').textContent='—';
 for(const id of ['uses-summary','outputs-summary','emissions-summary'])document.getElementById(id).textContent='กำลังอ่านข้อมูล';
 for(const node of document.querySelectorAll('[data-detail]'))node.removeAttribute('title');
 try {
  const params=new URLSearchParams({fuel:selectedFuel});
  if(period){const [year,month]=period.split('-');params.set('year',year);params.set('month',month);}
  const response=await fetch('/api/flow?'+params,{signal:controller.signal});if(!response.ok)throw new Error();
  flowData=await response.json();
  periodSelect.replaceChildren(...flowData.periods.map(p=>new Option(`${p.year}-${String(p.month).padStart(2,'0')}`,`${p.year}-${String(p.month).padStart(2,'0')}`)));
  periodSelect.value=`${flowData.year}-${String(flowData.month).padStart(2,'0')}`;
  document.querySelector('#flow-status').textContent='ปริมาณแยกตามหน่วยและแหล่งข้อมูล';
  for(const category of ['uses','outputs','emissions']) {
   document.getElementById(category+'-summary').textContent=`${flowData[category].length} รายการ · ชี้ดูปริมาณ`;
   for(const node of document.querySelectorAll(`[data-detail="${category}"]`))node.title=flowData[category].map(rowText).join('\n') || 'ไม่พบข้อมูลในเดือนที่เลือก';
  }
  document.querySelector('#input-quantity').textContent=flowData.uses.length ? `${flowData.uses.length} รายการ · ชี้ดูปริมาณ` : 'ไม่พบข้อมูล';
  showDetail(selectedDetail);
 } catch(error) {
  if(error.name==='AbortError')return;
  document.querySelector('#flow-status').textContent='อ่านข้อมูลไม่ได้ กรุณาลองเลือกเชื้อเพลิงอีกครั้ง';
  for(const id of ['uses-summary','outputs-summary','emissions-summary'])document.getElementById(id).textContent='ยังไม่มีข้อมูล';
  document.querySelector('#detail-rows').textContent='ยังอ่านปริมาณไม่ได้';
 }
}
periodSelect.addEventListener('change',()=>loadFlow(periodSelect.value));
for(const button of document.querySelectorAll('[data-tab]'))button.addEventListener('click',()=>showDetail(button.dataset.tab));
for(const node of document.querySelectorAll('[data-detail]')) {
 node.addEventListener('mouseenter',()=>{
  showDetail(node.dataset.detail);
  if(flowData){
   const rows=flowData[node.dataset.detail];
   tooltip.textContent=labels[node.dataset.detail]+'\n'+(rows.slice(0,3).map(rowText).join('\n') || 'ไม่พบข้อมูลเดือนนี้')+(rows.length>3?'\nดูรายการทั้งหมดด้านล่าง':'');tooltip.hidden=false;
  }
 });
 node.addEventListener('mouseleave',()=>{tooltip.hidden=true;});
 node.addEventListener('focus',()=>showDetail(node.dataset.detail));
 node.addEventListener('click',()=>showDetail(node.dataset.detail));
 node.addEventListener('keydown',event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();showDetail(node.dataset.detail);}});
}
loadFlow();
