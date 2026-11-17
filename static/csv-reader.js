// Decode doubled quotes, quoted newlines and the UTF-8 BOM in EPPO exports.
function csvRecords(text) {
  const rows = [];
  let row = [], cell = '', state = 'field';
  const source = text.replace(/^\uFEFF/, '');
  for (let i = 0; i < source.length; i++) {
    const c = source[i];
    if (state === 'quoted') {
      if (c !== '"') cell += c;
      else if (source[i + 1] === '"') { cell += '"'; i++; }
      else state = 'closed';
    } else if (c === ',') { row.push(cell); cell = ''; state = 'field'; }
    else if (c === '\n' || c === '\r') {
      row.push(cell); rows.push(row); row = []; cell = ''; state = 'field';
      if (c === '\r' && source[i+1] === '\n') i++;
    } else if (c === '"' && !cell && state === 'field') state = 'quoted';
    else if (state === 'closed' || c === '"') throw Error('รูปแบบเครื่องหมายคำพูดใน CSV ผิด');
    else cell += c;
  }
  if (state === 'quoted') throw Error('CSV มีข้อความที่ปิดเครื่องหมายคำพูดไม่ครบ');
  if (row.length || cell || state === 'closed') rows.push([...row, cell]);
  return rows;
}
const monthNames = 'January February March April May June July August September October November December'.split(' ');
const validUnits = new Set(['BBL/DAY','Million Litres','Million Litres/Day','MMSCFD','MMSCF','Thousand Tons','Ton','1,000 Tons','Thousand Tons-CO2']);
function readSource(code, text) {
  const [header, ...records] = csvRecords(text);
  const expected = sourceCatalog[code].header;
  if (!header || header.length !== expected.length || expected.some((h,i) => h !== header[i].trim()))
    throw Error('หัวคอลัมน์ไม่ตรงกับ ' + code + ' · ต้องเป็น ' + expected.join(', '));
  const amountIndex = code === 'SRC-15' ? 4 : 3;
  return records.map((fields,i) => {
    const [year,month,category] = fields.map(x => x.trim());
    const raw = fields[amountIndex] ?? '';
    const unit = (fields[amountIndex+1] ?? '').trim();
    const categoryKey = fields.slice(2,amountIndex).map(x=>x.trim()).join(' / ');
    const value = Number(raw.replaceAll(',',''));
    const m = monthNames.findIndex(name => name.toLowerCase() === month?.toLowerCase()) + 1;
    let status = 'VALID', reason = '';
    if (fields.length !== expected.length) reason = 'จำนวนคอลัมน์ไม่ตรง';
    else if (code === 'SRC-14' && category.toUpperCase() === 'TOTAL') {status='SKIPPED'; reason='แถวรวม ซ้ำกับรายชนิด';}
    else if (!/^\d{4}$/.test(year) || !m) reason = 'ปีหรือเดือนผิดรูปแบบ';
    else if (fields.slice(2,amountIndex).some(x=>!x.trim())) reason = 'ขาดชื่อรายการ';
    else if (code==='SRC-22' && !['DIESEL OIL','FUEL OIL','NATURAL GAS','LIGNITE','PALM OIL'].includes(category.toUpperCase())) reason='ไม่รู้จักเชื้อเพลิง กฟผ.';
    else if (code==='SRC-09' && !/^(PRODUCTION|CONSUMPTION|IMPORT$|EXPORT$)/i.test(category)) reason='ไม่รู้จักประเภท LPG';
    else if (code==='SRC-13' && !/^(PRODUCTION|CONSUMPTION)/i.test(category)) reason='ไม่รู้จักประเภทลิกไนต์';
    else if (!raw.trim() || /^null$/i.test(raw.trim())) reason = 'ไม่มีปริมาณ';
    else if (!/^[+]?(?:\d+(?:\.\d*)?|\d{1,3}(?:,\d{3})+(?:\.\d*)?|\.\d+)(?:e[+-]?\d+)?$/i.test(raw.trim()) || !Number.isFinite(value)) reason = 'ปริมาณไม่ถูกต้อง';
    else if (!validUnits.has(unit)) reason='หน่วยไม่อยู่ในรายการต้นทาง';
    if (reason && status==='VALID') status='ERROR';
    return {year,month,m,raw,unit,value,series:categoryKey+' · '+unit,category:categoryKey,status,reason,line:i+2,code};
  });
}
