(() => {
'use strict';
const $=id=>document.getElementById(id), M=EnergyModel;
const state={lang:'th',tab:'flow',view:'graph',year:0,month:0,fuel:'all',source:'',unit:'',needle:'',periods:[],units:[],rows:[],issues:[],log:false,busy:false,error:false,local:null,selection:null,page:0,issuePage:0,sort:'month',reverse:false,overrides:{}};
try{state.overrides=JSON.parse(sessionStorage.getItem('lci-unit-factors')||'{}')||{};}catch{}
let serial=0,importSerial=0,playTimer=null,dbPeriods=[],filtered=[],groups=[],buckets=new Map(),issueList=[],csvMessage='';
const t=(th,en)=>state.lang==='th'?th:en;
const num=n=>new Intl.NumberFormat('en-US',{maximumFractionDigits:6}).format(n);
const period=(y,m)=>m?y+'-'+String(m).padStart(2,'0'):String(y);
const fuelNames={all:['ทั้งหมด','All'],oil:['น้ำมัน','Oil'],gas:['ก๊าซธรรมชาติ','Natural Gas'],lpg:['LPG','LPG'],coal:['ถ่านหิน','Coal'],bio:['ชีวภาพ','Biofuel']};
const fieldNames=['flow','stage','type','process','direction','fuel','amount','unit','year','month','source','status','note'];
const fieldLabels=['Flow','Stage','Process type','Process','Direction','Fuel','Amount','Original unit','Year','Month','Source','Status','Note'];
const stages=['Upstream / Supply','Midstream','Refining & Processing','Distribution','End-use'];
const metric = (r,target=state.unit)=>M.amount(r,target,state.units,state.overrides);
const format = a=>a?num(a.value)+' '+a.unit:'N/A';
function options(element,pairs,value){
 const signature=JSON.stringify(pairs);
 if(element.dataset.items!==signature){element.replaceChildren(...pairs.map(([v,s])=>new Option(s,v)));element.dataset.items=signature;}
 element.value=String(value);
}
const unique=a=>[...new Set(a)];
function controls(){
 const years=unique(state.periods.map(p=>p.year)).sort((a,b)=>b-a);
 options($('year'),years.map(y=>[y,y]),state.year);
 const months=unique(state.periods.filter(p=>p.year===state.year&&p.month).map(p=>p.month)).sort((a,b)=>a-b);
 options($('month'),[[0,t('ทั้งปี','Whole year')],...months.map(m=>[m,String(m).padStart(2,'0')])],state.month);
 options($('fuel'),Object.entries(fuelNames).map(([k,v])=>[k,t(...v)]),state.fuel);
 const sources=unique([...state.rows,...state.issues].map(r=>r.source)).sort();
 options($('source'),[['',t('ทุกแหล่ง','All sources')],...sources.map(s=>[s,s])],state.source);
 const sourceUnits=unique(filtered.map(r=>r.unit));
 const targets=state.units.filter(u=>sourceUnits.some(s=>s!==u.symbol&&M.compatible(s,u.symbol,state.units)));
 if(!targets.some(u=>u.symbol===state.unit))state.unit='';
 options($('unit'),[['',t('หน่วยต้นฉบับ','Original unit')],...targets.map(u=>[u.symbol,u.symbol])],state.unit);
 const steps=state.periods.filter(p=>p.month);
 $('time').max=Math.max(0,steps.length-1);$('time').disabled=!steps.length||state.busy;
 $('time').value=Math.max(0,steps.findIndex(p=>p.year===state.year&&(!state.month||p.month===state.month)));
 $('when').textContent=period(state.year,state.month);$('period-label').textContent=$('when').textContent;
 $('play').disabled=!steps.length||state.error;
 $('play').textContent=playTimer?'Ⅱ '+t('หยุด','Pause'):'▶ '+t('เล่น','Play');
 options($('sort'),fieldNames.map((f,i)=>[f,fieldLabels[i]]),state.sort);
}
function kpis(){
 const root=$('kpis');root.replaceChildren();
 for(const [role,name] of [['supply','SUPPLY'],['demand','DEMAND'],['emission','CO₂']]){
  const rows=filtered.filter(r=>M.accepted(r)&&r.role===role);
  const series=[...M.groupRows(rows).values()];
  let value=null;
  // ผลรวมใช้สาขาเดียวกับหน่วยเดียว หลีกเลี่ยง SRC ที่ซ้อนขอบเขตกัน
  const quantities=series.map(s=>metric(s,role==='emission'?'':state.unit));
  const oneSource=unique(rows.map(r=>r.source)).length===1;
  const sameCoverage=unique(series.map(s=>s.map(r=>r.month).sort((a,b)=>a-b).join('-'))).length===1;
  if(oneSource && sameCoverage && quantities.length && quantities.every(q=>q&&q.unit===quantities[0]?.unit)
    && (role==='emission'||unique(rows.map(r=>r.flow)).length===1))
    value={unit:quantities[0].unit,value:quantities.reduce((n,q)=>n+q.value,0)};
  const sources=unique(rows.map(r=>r.source)).sort().join(', ');
  const explanation=[sources||t('ไม่มีแหล่งที่ตรงเงื่อนไข','No matching source'),
    t('รวมเฉพาะแถวที่ผ่านการตรวจภายในแหล่งเดียวและมีหน่วยกับช่วงเดือนตรงกัน','Sum validated series from one source with matching units and month coverage'),
    role==='emission'?t('CO₂ ตามที่รายงานใน SRC-18–21 แยกสาขาและใช้หน่วยเดิม','Reported CO₂ in SRC-18–21, by sector in original units'):t('ต้องเป็น Flow เดียวกัน อัตรารายวันถ่วงตามจำนวนวันจริง','One flow required. Daily rates use a day-weighted average'),
    value?t('เดือนที่มีข้อมูล','Observed months')+' '+unique(rows.map(r=>r.month)).sort((a,b)=>a-b).join(', '):t('เลือกแหล่ง เชื้อเพลิง หรือ Flow ให้แคบลงเมื่อขอบเขตซ้อนกัน','Narrow source, fuel or flow when scopes overlap')].join(' · ');
  const details=document.createElement('details'), summary=document.createElement('summary'), strong=document.createElement('strong'),p=document.createElement('p');
  summary.textContent=name+' ⓘ';strong.textContent=format(value);summary.append(strong);summary.title=explanation;p.textContent=explanation;details.append(summary,p);root.append(details);
 }
}
function tableRow(table,values,heading=false){const tr=table.insertRow();for(const val of values){const c=document.createElement(heading?'th':'td');c.textContent=val??'—';tr.append(c);}}
function sortedRows(){return [...filtered].sort((a,b)=>String(a[state.sort]??'').localeCompare(String(b[state.sort]??''),'en',{numeric:true})*(state.reverse?-1:1));}
function table(){
 const rows=sortedRows(),el=$('records');el.replaceChildren();
 tableRow(el,fieldLabels,true);const pages=Math.max(1,Math.ceil(rows.length/50));
 state.page=Math.min(state.page,pages-1);for(const row of rows.slice(state.page*50,state.page*50+50))tableRow(el,fieldNames.map(k=>k==='stage'?stages[row.stage]:row[k]));
 $('prev').disabled=!state.page;$('next').disabled=state.page+1>=pages;$('page').textContent=(state.page+1)+' / '+pages+' · '+num(rows.length)+' '+t('แถว','rows');
 $('export').disabled=!rows.length;
}
function side(){
 const detail=$('details'),g=groups.find(g=>g.id===state.selection);
 detail.hidden=!g;detail.replaceChildren();if(!g)return;
 const close=document.createElement('button');close.textContent='×';close.setAttribute('aria-label',t('ปิด','Close'));close.onclick=()=>{state.selection=null;render();};
 const title=document.createElement('h3');title.textContent=g.flow;detail.append(close,title);
 for(const text of [g.process,stages[g.stage],g.amount,g.period,g.source+' · '+g.status]){
  const p=document.createElement('p');p.textContent=text;detail.append(p);
 }
 const tb=document.createElement('table');tableRow(tb,['Month','Amount','Unit'],true);
 for(const r of buckets.get(g.id)||[])tableRow(tb,[r.month,r.amount,r.unit]);detail.append(tb);
}
function render(){
 const s=state;document.documentElement.lang=s.lang;
 document.querySelectorAll('[data-en]').forEach(el=>el.textContent=el.dataset[s.lang]);
 $('lang').textContent=s.lang==='th'?'EN':'ไทย';
 document.querySelectorAll('[data-tab]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.tab===s.tab)));
 filtered=s.rows.filter(r=>(!s.month||r.month===s.month)&&(s.fuel==='all'||s.fuel===r.fuel)&&(!s.source||s.source===r.source)&&(!s.needle||[r.flow,r.process,r.source,r.status,r.note].join(' ').toLowerCase().includes(s.needle)));
 controls();kpis();buckets=M.groupRows(filtered);
 groups=[...buckets].map(([id,rs])=>{const r=rs[0],a=metric(rs,r.role==='emission'?'':s.unit);return {id,stage:r.stage,fuel:r.role==='emission'?'co2':r.fuel,label:r.flow,process:r.process,flow:r.flow,amount:format(a),period:period(s.year,s.month)+(s.month?'':' · '+unique(rs.map(r=>r.month)).length+'/12'),source:r.source,status:r.status};});
 const mode=s.local?t('ไฟล์ในเครื่อง','Local CSV'):t('ฐานข้อมูล PostgreSQL','PostgreSQL');
 $('state').textContent=[mode,s.busy?t('กำลังโหลด','Loading…'):s.error?t('อ่านฐานข้อมูลไม่ได้ ลองเลือกปีอีกครั้งหรือเปิด CSV','Database unavailable. Retry the year or open CSV files'):filtered.length?num(filtered.length)+' '+t('รายการ','records'):t('ไม่มีข้อมูลตามตัวกรอง','No matching records'),csvMessage,
 s.unit?t('แปลงเฉพาะหน่วยที่เข้ากันได้ รายการอื่นคงหน่วยเดิม','Compatible units converted. Other records retain their units'):'',
 s.unit&&Object.keys(s.overrides).length?t('ใช้ตัวคูณทดลองของเซสชัน','Session factors active'):''].filter(Boolean).join(' · ');
 $('flow').hidden=s.tab!=='flow';$('analysis-body').hidden=s.tab==='flow';$('restore').hidden=!s.local;
 $('graph-wrap').hidden=s.view!=='graph';$('table-wrap').hidden=s.view!=='table';
 for(const v of ['graph','table'])$(v+'-view').setAttribute('aria-pressed',String(s.view===v));
 if(s.tab==='flow' && s.view==='graph'){
   side();window.energyScene.render(groups,{lang:s.lang,selected:s.selection,onSelect:id=>{s.selection=id;render();}});
 }else if(s.tab==='flow')table();
 else window.energyAnalysis.render({...s,rows:filtered,onFactorChange:(symbol,value)=>{if(value===null)delete s.overrides[symbol];else s.overrides[symbol]=value;try{sessionStorage.setItem('lci-unit-factors',JSON.stringify(s.overrides));}catch{}render();}});
 renderInfo();
}


function renderInfo(){
 const s=state;
 $('snapshot').textContent=t('Snapshot จากรายงาน 16 พ.ย. 2569 · VERIFIED 42,599 Exchange จาก 22 แหล่ง · SKIPPED 487 · ERROR 108 · UNIT 13 หน่วย · SRC-22 นำเข้า 1,878 จาก 1,982 แถว อีก 104 แถวขาดปริมาณ','Report snapshot · 16 Nov 2026 · 42,599 VERIFIED exchanges, 22 sources, 487 skipped, 108 errors and 13 units. SRC-22 contained 1,982 rows, including 104 missing quantities.');
 $('serving').textContent=t('ตามรายงาน 16 พ.ย. 2569 ข้อมูล Serving Layer ตรงกับ PostgreSQL 42,599 Exchange จาก 22 แหล่ง · PostgreSQL บน Render เป็นฐานหลัก · Neo4j เชื่อม Process, Exchange, Flow, Source และ Unit โดยซิงก์ Aura เมื่อ 17 พ.ย. · SQL ใช้บน Render และ Cypher ใช้ในเครื่องที่เชื่อม Neo4j · multilingual MiniLM สร้างเวกเตอร์ 384 มิติสำหรับ pgvector · Gemini Flash Lite สรุปหลักฐานพร้อมรหัส SRC และ Exchange คะแนน similarity วัดความใกล้เคียงของข้อความ','Report snapshot, 16 Nov 2026: serving data matched PostgreSQL at 42,599 exchanges and 22 sources. Render hosts PostgreSQL. Neo4j links Process, Exchange, Flow, Source and Unit; Aura synced on 17 Nov. SQL runs on Render and local Cypher uses Neo4j. pgvector retrieves 384-dimensional multilingual MiniLM embeddings. Gemini Flash Lite cites source and exchange IDs. Similarity measures textual proximity.');
 issueList=s.issues.filter(i=>(!s.source||i.source===s.source)&&(!s.month||i.month===s.month));
 $('quality').textContent=[period(s.year,s.month),t('บันทึกนำเข้าตามแหล่งและช่วงเวลา','Import log by source and period'),s.log?'ERROR '+issueList.filter(i=>i.status==='ERROR').length+' · SKIPPED '+issueList.filter(i=>i.status==='SKIPPED').length:t('ไม่มีบันทึกให้ตรวจ','Log unavailable'),t('คำนวณสมดุลไม่ได้จากข้อมูลที่มี เนื่องจากขอบเขตต่างกันและข้อมูล stock change, own use, flaring และ loss ไม่ครบ','Balance unavailable: incompatible scopes and incomplete stock change, own use, flaring and loss data.')].join(' · ');
 const issues=$('issues');issues.replaceChildren();
 if(issueList.length){tableRow(issues,['Source','Year','Month','Row','Status','Reason'],true);s.issuePage=Math.min(s.issuePage,Math.ceil(issueList.length/40)-1);
 for(const i of issueList.slice(s.issuePage*40,s.issuePage*40+40))tableRow(issues,[i.source,i.year,i.month,i.line,i.status,i.reason]);}
 const nav=$('issue-nav');nav.replaceChildren();if(issueList.length>40)for(const [title,step] of [['‹',-1],['›',1]]){
 const b=document.createElement('button');b.textContent=title;b.disabled=s.issuePage+step<0||(s.issuePage+step)*40>=issueList.length;
 b.onclick=()=>{s.issuePage+=step;renderInfo();};nav.append(b);}
}
async function json(path){
 const res=await fetch('/api/energy/'+path);if(!res.ok)throw Error('Database unavailable');return res.json();
}
async function loadYear(year,month){
 const token=++serial,s=state;s.year=Number(year);s.month=Number(month)||0;s.rows=[];s.issues=[];s.selection=null;s.page=0;s.busy=true;s.error=false;s.log=false;render();
 try{
  const d=s.local?{rows:s.local.rows.filter(r=>r.year===s.year),issues:s.local.issues.filter(r=>r.year===s.year),log_available:true}:await json('rows?year='+s.year);
  if(token!==serial)return;
  s.rows=d.rows.map(r=>({...r,type:r.type||r.process_type}));s.issues=d.issues;s.log=d.log_available;
 }catch{if(token!==serial)return;s.error=true;stop();}
 if(token===serial){s.busy=false;render();}
}
function chooseYear(){const ys=unique(state.periods.map(p=>p.year)).sort((a,b)=>b-a);return ys.find(y=>state.periods.filter(p=>p.year===y&&p.month).length===12)||ys[0]||0;}
async function database(){
 ++importSerial;const token=++serial;stop();Object.assign(state,{local:null,busy:true,error:false,rows:[],issues:[],periods:[],source:'',units:[],year:0,month:0,log:false});csvMessage='';render();
 try{const [p,u]=await Promise.all([json('periods'),json('units')]);if(token!==serial)return;
 dbPeriods=p.periods;state.periods=dbPeriods;state.units=u.units;await loadYear(chooseYear(),0);
 }catch{if(token!==serial)return;state.busy=false;state.error=true;render();}
}
async function importFiles(files){
 const ticket=++importSerial,rows=[],issues=[],sources=new Set(),errors=[]; stop();
 for(const file of files){
  const code=file.name.toUpperCase().replace(/\.CSV$/,'');
  try {
   if(!Object.hasOwn(sourceCatalog,code)||!file.name.toLowerCase().endsWith('.csv'))throw Error('SRC-01.csv … SRC-22.csv');
   if(sources.has(code))throw Error(t('แหล่งซ้ำ','Duplicate source'));
   const raw=readSource(code,await file.text());sources.add(code);
   for(const r of raw){if(!['ERROR','SKIPPED'].includes(r.status))rows.push(M.csvRow(r));
    else issues.push({source:code,line:r.line,month:r.m,year:Number(r.year),status:r.status,reason:r.reason});}
  }catch(e){errors.push(file.name+' · '+e.message);}
 }
 if(ticket!==importSerial)return;
 ++serial;state.local={rows,issues};state.source='';state.periods=unique([...rows,...issues].filter(r=>r.year).map(r=>JSON.stringify([r.year,r.month]))).map(p=>{const [year,month]=JSON.parse(p);return {year,month};}).sort((a,b)=>a.year-b.year||a.month-b.month);
 const missing=Object.keys(sourceCatalog).filter(c=>!sources.has(c));csvMessage=[...errors,missing.length?t('ไม่มีชุดข้อมูล ','Missing sources ')+missing.join(', '):''].filter(Boolean).join(' · ');
 await loadYear(chooseYear(),0);
}
$('files').onchange=e=>{if(e.target.files.length)importFiles([...e.target.files]);e.target.value='';};
$('restore').onclick=database;
$('year').onchange=e=>{stop();loadYear(e.target.value,0);};
function stop(){if(playTimer)clearInterval(playTimer);playTimer=null;}
const months=()=>state.periods.filter(p=>p.month);
function jump(idx){
 const next=months()[idx];if(!next)return;
 if(state.year!==next.year)loadYear(next.year,next.month);else{state.month=next.month;state.selection=null;state.page=0;render();}
}
$('time').oninput=e=>{stop();jump(Number(e.target.value));};
$('play').onclick=()=>{if(playTimer)stop();else{const step=()=>{if(state.busy)return;const ps=months(),i=ps.findIndex(p=>p.year===state.year&&p.month===state.month);
  const start=ps.findIndex(p=>p.year===state.year);jump(i<0?Math.max(0,start):(i+1)%ps.length);};playTimer=setInterval(step,1350);step();}render();};
for(const key of ['month','fuel','source','unit','sort']){
 $(key).onchange=e=>{stop();state[key]=key==='month'?Number(e.target.value):e.target.value;state.page=0;state.issuePage=0;state.selection=null;render();};
}
$('needle').oninput=e=>{state.needle=e.target.value.trim().toLowerCase();state.selection=null;state.page=0;render();};
$('reverse').onclick=()=>{state.reverse=!state.reverse;state.page=0;table();};
$('prev').onclick=()=>{state.page--;table();};$('next').onclick=()=>{state.page++;table();};
$('export').onclick=()=>{
 const quote=x=>'"'+String(x??'').replaceAll('"','""')+'"';
 const csv=[fieldLabels,...sortedRows().map(r=>fieldNames.map(k=>k==='stage'?stages[r.stage]:r[k]))].map(row=>row.map(quote).join(',')).join('\r\n');
 const url=URL.createObjectURL(new Blob(['\uFEFF',csv],{type:'text/csv;charset=utf-8'}));
 const a=document.createElement('a');a.href=url;a.download='LCI-'+period(state.year,state.month)+'.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
};
for(const tab of document.querySelectorAll('[data-tab]'))tab.onclick=()=>{stop();state.tab=tab.dataset.tab;render();};
for(const v of ['table','graph'])$(v+'-view').onclick=()=>{state.view=v;render();};
$('lang').onclick=()=>{state.lang=state.lang==='th'?'en':'th';render();};
window.addEventListener('three-ready',()=>render());
document.addEventListener('visibilitychange',()=>{if(document.hidden && playTimer){stop();render();}});
if(location.protocol==='file:'){state.local={rows:[],issues:[]};render();}else database();
})();
