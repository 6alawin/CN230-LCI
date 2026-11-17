(() => {
  const byId = id => document.getElementById(id);
  const local = new Map(), cache = new Map();
  const origin = byId('origin'), src = byId('src'), years = byId('chart-year'), series = byId('series');
  let current = [], revision = 0, selection = 0;
  const codes = Object.keys(sourceCatalog);
  function options(select, pairs, preferred) {
    select.replaceChildren(...pairs.map(([value,label]) => new Option(label,value)));
    if (pairs.some(([value])=>value===preferred)) select.value=preferred;
  }
  options(src,codes.map(code=>[code,code+' · '+sourceCatalog[code].title]),'SRC-21');
  for (const button of document.querySelectorAll('[data-panel]')) button.onclick = () => {
    for (const tab of document.querySelectorAll('[data-panel]')) {
      const active = tab===button;
      tab.setAttribute('aria-pressed',String(active)); byId(tab.dataset.panel).hidden=!active;
    }
    if (button.dataset.panel==='charts') load();
  };
  function updateSeries() {
    const rows = current.filter(r=>r.year===years.value);
    const items = [...new Set(rows.map(r=>r.series))].sort();
    options(series,items.map(s=>[s,s]),series.value);
    draw();
  }
  function draw() {
    const rows = current.filter(r=>r.year===years.value && r.series===series.value).sort((a,b)=>a.m-b.m);
    const accepted = rows.filter(r=>r.status==='VALID');
    const max = accepted.reduce((n,r)=>Math.max(n,r.value),0);
    const bars=byId('bars'), raw=byId('raw'); bars.replaceChildren(); raw.replaceChildren();
    for (const row of accepted) {
      const div=document.createElement('div'); div.className='bar-row';
      const name=document.createElement('span'), bar=document.createElement('i'), amount=document.createElement('span');
      name.textContent=row.month; bar.style.width=(max ? row.value/max*100 : 0)+'%'; amount.textContent=row.raw;
      div.append(name,bar,amount); bars.append(div);
    }
    for (const row of rows.filter(r=>!byId('row-state').value || r.status===byId('row-state').value)) {
      const tr=raw.insertRow();
      for (const field of [row.code+'.csv #'+row.line,row.year,row.month,row.category,row.raw || 'ว่าง',row.unit,row.status,row.reason || '—'])
        tr.insertCell().textContent=field;
    }
  }
  function counts(rows) {
    const n={VALID:0,ERROR:0,SKIPPED:0};
    for (const row of rows) n[row.status]++;
    return Object.entries(n).map(([key,v])=>key+' '+v.toLocaleString('en-US')).join(' · ');
  }
  async function load() {
    const run=++revision, code=src.value;
    current=[]; years.replaceChildren(); series.replaceChildren(); draw();
    byId('csv-status').textContent='กำลังอ่าน '+code;
    byId('chart-source').replaceChildren();
    try {
      let rows;
      if(origin.value==='local') rows=local.get(code);
      else {
        if(!cache.has(code)){
          const response=await fetch('/api/source-csv/'+code);
          if(!response.ok) throw Error('เปิดไฟล์จากโปรเจกต์ไม่ได้');
          cache.set(code,readSource(code,await response.text()));
        }
        rows=cache.get(code);
      }
      if(run!==revision)return;
      if(!rows) throw Error('ไม่มีข้อมูลชุด '+code+' ในไฟล์ที่เลือก');
      current=rows; byId('csv-status').textContent=code+' · '+counts(rows);
      const values=[...new Set(rows.map(r=>r.year))].sort().reverse();
      options(years,values.map(y=>[y,y]),values.includes('2025')?'2025':values[0]);
      updateSeries();
      const link=document.createElement('a');link.href=sourceCatalog[code].url;link.textContent='EPPO · '+sourceCatalog[code].title;
      byId('chart-source').append(link);
    } catch(e){if(run===revision)byId('csv-status').textContent=e.message;}
  }
  byId('csv-files').onchange=async event=>{
    const run=++selection, imported=new Map(), errors=[];
    for(const file of event.target.files){
      const match=/^(SRC-(?:0[1-9]|1\d|2[0-2]))\.csv$/i.exec(file.name);
      try {
        if(!match)throw Error('ชื่อไฟล์ต้องเป็น SRC-01.csv ถึง SRC-22.csv');
        const code=match[1].toUpperCase();
        if(imported.has(code))throw Error('เลือกแหล่งนี้ซ้ำ');
        imported.set(code,readSource(code,await file.text()));
      } catch(e){errors.push(file.name+' · '+e.message);}
    }
    if(run!==selection)return;
    local.clear(); for(const [code,rows] of imported)local.set(code,rows);
    const missing=codes.filter(c=>!local.has(c));
    byId('file-status').textContent=['อ่านได้ '+local.size+'/22 แหล่ง',...errors,missing.length?'ไม่มีข้อมูล '+missing.join(', '):''].filter(Boolean).join(' · ');
    byId('quality-local').textContent=local.size+' แหล่ง · '+counts([...local.values()].flat());
    origin.value='local'; if(local.size) src.value=local.keys().next().value;
    load();
  };
  src.onchange=origin.onchange=load; years.onchange=updateSeries; series.onchange=byId('row-state').onchange=draw;
  if(location.protocol==='file:'){origin.value='local';origin.options[0].disabled=true;}
})();
