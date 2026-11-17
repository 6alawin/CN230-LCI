/* global document, window */
(() => {
  'use strict';
  const selected = { source: '', series: '', period: 'month' };
  const safeStatus = new Set(['VERIFIED', 'VALID']);
  const additiveUnits = new Set(['MMSCF', 'Ton', '1,000 Tons', 'Thousand Tons', 'Thousand Tons-CO2', 'Million Litres']);
  const rateUnits = new Set(['BBL/DAY', 'MMSCFD', 'Million Litres/Day']);
  const numberFormat = new Intl.NumberFormat('en-US', { maximumFractionDigits: 8 });
  const element = (name, text, className) => {
    const item = document.createElement(name);
    if (text !== undefined) item.textContent = text;
    if (className) item.className = className;
    return item;
  };
  function render({ lang, units = [], rows = [], overrides = {}, onFactorChange, tab }) {
    const mount = document.getElementById('analysis-body');
    if (!mount) return;
    const en = lang === 'en';
    const tr = (th, eng) => en ? eng : th;
    const monthLabel = new Intl.DateTimeFormat(en ? 'en-GB' : 'th-TH', {month:'short',timeZone:'UTC'});
    mount.replaceChildren();
    function note(text) { mount.append(element('p', text, 'analysis-note')); }
    function inputSelect(parent, label, pairs, value, change) {
      const outer = element('label', label);
      const select = element('select');
      for (const [id,text] of pairs) select.add(new Option(text,id));
      select.value = value;
      select.onchange = () => change(select.value);
      outer.append(select); parent.append(outer);
    }
    if (tab.toLowerCase() === 'factors') {
      mount.append(element('h2', tr('ตัวคูณแปลงหน่วย','Unit conversion factors')));
      note(tr('ค่าอ้างอิงจากตาราง UNIT · หน่วยต้นทาง × ตัวคูณของหน่วยต้นทาง ÷ ตัวคูณของหน่วยปลายทาง ใช้เมื่อชนิดปริมาณและฐานหน่วยตรงกัน',
        'Reference values from UNIT. For compatible quantities with a common base unit, multiply by the source factor and divide by the target factor.'));
      if (!units.length) {
        note(tr('ไม่มีข้อมูลตาราง UNIT สำหรับชุดข้อมูลนี้','No UNIT records are available for this dataset.'));
      } else {
        note(tr('ค่าทดลองมีผลเฉพาะเซสชันนี้และยังไม่ได้รับการยืนยันจากต้นทาง','Session overrides are experimental values and have no source verification.'));
        const wrap = element('div',undefined,'table-scroll');
        const table = element('table');
        const head = table.createTHead().insertRow();
        for (const title of ['symbol','quantity_type','to_base_factor',tr('ตัวคูณในเซสชัน','Session factor')]) head.append(element('th',title));
        const body = table.createTBody();
        for (const item of units) {
          const trEl = body.insertRow();
          for (const field of ['symbol','quantity_type','to_base_factor']) trEl.insertCell().textContent=item[field] ?? '—';
          const cell = trEl.insertCell();
          const editor = element('form',undefined,'factor-editor');
          const field = element('input');
          field.type = 'number'; field.step = 'any'; field.min = '0'; field.required = true;
          field.value = overrides[item.symbol] ?? item.to_base_factor ?? '';
          field.setAttribute('aria-label',tr('ตัวคูณทดลองสำหรับ ','Session factor for ')+item.symbol);
          field.style.width='8em';
          const save=element('button',tr('ใช้ค่า','Apply')); save.type='submit';
          const reset=element('button',tr('คืนค่าต้นทาง','Restore')); reset.type='button';
          reset.disabled = !Object.prototype.hasOwnProperty.call(overrides,item.symbol);
          field.oninput=()=>field.setCustomValidity('');
          editor.onsubmit = event => {
            event.preventDefault();
            const value = field.valueAsNumber;
            if (!(value>0 && Number.isFinite(value))) {
              field.setCustomValidity(tr('ระบุจำนวนที่มากกว่า 0','Enter a positive number.'));
              field.reportValidity(); return;
            }
            onFactorChange(item.symbol,value);
          };
          reset.onclick = () => onFactorChange(item.symbol,null);
          editor.append(field,save,reset); cell.append(editor);
        }
        wrap.append(table);mount.append(wrap);
      }
      mount.append(element('h3',tr('ตัวคูณการปล่อย','Emission factors')));
      note(tr('ไม่มีข้อมูล emission factor ใน Schema ปัจจุบัน','The current schema contains no emission factors.'));
      return;
    }
    mount.append(element('h2',tr('แนวโน้มตามแหล่งข้อมูล','Trends by source')));
    // คงชุดข้อมูล กระบวนการ เชื้อเพลิง หน่วย และทิศทางเดียวกันต่อหนึ่งซีรีส์
    const eligible = rows.filter(r => safeStatus.has(r.status) && r.amount != null &&
      String(r.amount).trim() !== '' && Number.isFinite(Number(r.amount)) && Number(r.amount)>=0 &&
      Number.isInteger(+r.year) && +r.month>=1 && +r.month<=12);
    if (!eligible.length) {
      note(tr('ไม่มีแถวที่ผ่านการตรวจตามตัวกรองนี้','No validated records match these filters.'));
      return;
    }
    const sources=Array.from(new Set(eligible.map(r=>r.source))).sort();
    if(!sources.includes(selected.source)) selected.source=sources.includes('SRC-18')?'SRC-18':sources[0];
    const series = new Map();
    for(const row of eligible) {
      if(row.source!==selected.source) continue;
      const id=JSON.stringify([row.flow,row.process,row.type,row.direction,row.fuel,row.unit]);
      if(!series.has(id)) series.set(id,[]);
      series.get(id).push(row);
    }
    const choices=Array.from(series,([key,points])=> {
      const r=points[0];
      return [key,[r.flow,r.process,r.type,r.direction,r.unit].filter(Boolean).join(' · ')];
    }).sort((a,b)=>a[1].localeCompare(b[1]));
    if(!series.has(selected.series))selected.series=choices[0][0];
    const points=series.get(selected.series);
    const controls=element('div',undefined,'toolbar');
    const rerender = () => render({lang,units,rows,overrides,onFactorChange,tab});
    inputSelect(controls,tr('แหล่งข้อมูล','Source'),sources.map(s=>[s,s]),selected.source,v=>{selected.source=v;rerender();});
    inputSelect(controls,tr('Flow / กระบวนการ / หน่วย','Flow / process / unit'),choices,selected.series,v=>{selected.series=v;rerender();});
    inputSelect(controls,tr('ช่วงเวลา','Interval'),[['month',tr('รายเดือน','Monthly')],['year',tr('รายปี','Yearly')]],selected.period,v=>{selected.period=v;rerender();});
    mount.append(controls);
    const unit=points[0].unit;
    const periods=new Map();
    for(const r of points){
      const key=Number(r.year)*100+Number(r.month);
      if(!periods.has(key))periods.set(key,[]);
      periods.get(key).push(r);
    }
    const plot=[];
    const years=Array.from(new Set(points.map(r=>+r.year))).sort((a,b)=>a-b);
    // เดือนที่ไม่มีข้อมูลแสดงเป็นช่องว่าง ศูนย์เป็นค่าที่ต้นทางรายงานจริง
    const knownRate=rateUnits.has(unit);
    for(const year of years){
      let annual=0, days=0, available=0, ambiguous=false;
      for(let month=1;month<=12;month++){
        const records=periods.get(year*100+month) || [];
        const label=monthLabel.format(new Date(Date.UTC(2000,month-1,1)))+' '+year;
        if(selected.period==='month'){
          if(!records.length)plot.push({label,value:null,display:'—'});
          records.forEach((r,i)=>plot.push({label:records.length>1?label+' #'+(i+1):label,value:Number(r.amount),display:String(r.amount)}));
        }
        if(records.length>1){ambiguous=true;continue;}
        if(!records.length)continue;
        const periodDays=new Date(Date.UTC(year,month,0)).getUTCDate();
        available++;
        annual+=Number(records[0].amount)*(knownRate?periodDays:1);
        days+=periodDays;
      }
      if(selected.period==='year'){
        const valid = available && !ambiguous && (knownRate || additiveUnits.has(unit));
        const value=valid?(knownRate?annual/days:annual):null;
        plot.push({label:year+' · '+available+'/12',value,display:value===null?'N/A':numberFormat.format(value)});
      }
    }
    const titles=element('h3',points[0].flow+' · '+unit); mount.append(titles);
    if(selected.period==='year'){
      note(knownRate?tr('ค่าเฉลี่ยของอัตรารายวันที่ถ่วงน้ำหนักด้วยจำนวนวันปฏิทิน เฉพาะเดือนที่แสดงในตัวกรอง','Daily rate weighted by calendar days in the selected months.'):
        tr('รวมปริมาณเฉพาะเดือนที่อยู่ในตัวกรอง ป้ายกำกับแสดงจำนวนเดือนที่มีข้อมูลจาก 12 เดือน','Quantities are summed over the filtered months. Labels show the number of observed months out of 12.'));
      if(plot.some(p=>p.value===null))note(tr('N/A เมื่อมีค่าซ้ำในเดือนเดียวกัน หรือหน่วยไม่รองรับการรวมรายปี','N/A indicates repeated measurements for a month or a unit without a defined yearly aggregation.'));
    }
    const max=plot.reduce((largest,p)=>Math.max(largest,p.value??0),0);
    const chart=element('div',undefined,'analysis-plot');
    for(const p of plot){
      const row=element('div',undefined,'bar-row');
      row.style.display='grid';row.style.gridTemplateColumns='minmax(6em,auto) minmax(2em,1fr) minmax(5em,auto)';row.style.gap='0.7em';row.style.alignItems='center';row.style.margin='0.45em 0';
      const bar=element('i');bar.style.display='block';bar.style.height='0.65em';bar.style.borderRadius='0.2em';bar.style.background='var(--accent,#32aa99)';bar.style.width=(p.value && max?p.value/max*100:0)+'%';
      row.append(element('span',p.label),bar,element('span',p.display));chart.append(row);
    }
    mount.append(chart);
    note(selected.source+' · '+points[0].process+' · '+points[0].direction+' · '+Array.from(new Set(points.map(r=>r.status))).join(', '));
  }
  window.energyAnalysis={render};
})();
