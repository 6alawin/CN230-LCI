const EnergyModel = (() => {
  const accepted = r => ['VALID','VERIFIED'].includes(r.status);
  const families = [
    ['L','Million Litres'], ['BBL/DAY','L/day','Million Litres/Day'],
    ['MMSCFD','scf/day'], ['kg','Ton','Thousand Tons','1,000 Tons']
  ];
  const rate = unit => /\/day$|^MMSCFD$/i.test(unit);
  function compatible(a,b,units) {
    if(a===b)return true;
    return families.some(group=>group.includes(a)&&group.includes(b)) &&
      units.some(x=>x.symbol===a && units.some(y=>y.symbol===b && y.quantity_type===x.quantity_type));
  }
  function display(row,target,units,overrides) {
    if(!target || row.unit===target || !compatible(row.unit,target,units))return [Number(String(row.amount).replaceAll(',','')),row.unit];
    const factor = s=>Number(overrides[s] ?? units.find(u=>u.symbol===s)?.to_base_factor);
    return [Number(String(row.amount).replaceAll(',',''))*factor(row.unit)/factor(target),target];
  }
  function groupRows(rows) {
    const result=new Map();
    for(const row of rows){
      const id=JSON.stringify([row.stage,row.source,row.flow,row.process,row.unit,row.direction,row.status]);
      if(!result.has(id))result.set(id,[]);
      result.get(id).push(row);
    }
    return result;
  }
  // อัตราเฉลี่ยรายวันต้องถ่วงตามจำนวนวันในเดือน การบวกอัตราข้ามเดือนทำให้ยอดสูงเกินจริง
  function amount(rows,target,units,overrides) {
    if(!rows.length || rows.some(r=>!accepted(r)))return null;
    let sum=0,days=0,unit=null; const seen=new Set();
    for(const row of rows){
      const [value,u]=display(row,target,units,overrides);
      if((unit && unit!==u)||!Number.isFinite(value)||seen.has(row.month))return null;
      seen.add(row.month);unit=u;
      const weight=rate(u) && row.month?new Date(Date.UTC(row.year,row.month,0)).getUTCDate():1;
      sum+=value*weight; days+=weight;
    }
    return {value:rate(unit)?sum/days:sum,unit};
  }
  function csvRow(row){
    const n=Number(row.code.slice(4)), cat=row.category, upper=cat.toUpperCase();
    let flow=cat,process='NATIONAL',type='',fuel='oil';
    if([1,2,3,4,10,11,12,16,17].includes(n)){
      flow=({1:'Crude oil',2:'Condensate',3:'Crude oil',4:'Crude oil',10:'Natural gas',11:'Natural gas',12:'NGL',16:'B100',17:'Ethanol'})[n];
      process=n>=16?'NATIONAL':cat;
    }
    if([9,13].includes(n)){flow=n===9?'LPG':'LIGNITE';process=cat.match(/\((.*)\)/)?.[1]||'NATIONAL';}
    if(n===15){[flow,process]=cat.split(' / ');}
    if(n>=18 && n<=21){flow='CO2 - '+cat;process=['OTHER ECONOMIC SECTORS','INDUSTRY','TRANSPORT','ELECTRICITY GENERATION'][n-18];}
    if(n===22)process='ELECTRICITY (EGAT)';
    if([1,2,5,16,17].includes(n))type='PRODUCTION';
    if([3,6,14].includes(n))type='IMPORT';
    if(n===4)type='REFINING';
    if(n===7)type='EXPORT';
    if([8,11,15,22].includes(n))type='DOMESTIC_USE';
    if([9,13].includes(n))type=upper.startsWith('PRODUCTION')?'PRODUCTION':upper.startsWith('CONSUMPTION')?'DOMESTIC_USE':upper;
    if(n===10)type=['LNG','YADANA','ZAWTIKA'].includes(upper)?'IMPORT':'PRODUCTION';
    if(n===12)type=upper==='EXPORT'?'EXPORT':'DISTRIBUTION';
    if(n>=18&&n<=21)type='EMISSION';
    if([10,11,12].includes(n)||/NATURAL GAS/.test(upper))fuel='gas';
    if([13,14,15].includes(n)||/LIGNITE|COAL/.test(upper))fuel='coal';
    if([16,17].includes(n)||/PALM OIL/.test(upper))fuel='bio';
    if(n===9||flow.toUpperCase()==='LPG')fuel='lpg';
    const role=type==='EMISSION'?'emission':type==='DOMESTIC_USE'?'demand':['IMPORT','PRODUCTION'].includes(type)?'supply':null;
    let stage=0;
    if(type==='DISTRIBUTION'||type==='EXPORT')stage=3;
    if(type==='REFINING'||(type==='PRODUCTION'&&[5,9,16,17].includes(n)))stage=2;
    if(role==='emission'||role==='demand')stage=4;
    if((n===12&&type==='DISTRIBUTION')||(n===11&&upper==='GSP'))stage=1;
    return {source:row.code,id:row.line,flow,process,type,role,stage,fuel,unit:row.unit,amount:row.raw,
      status:row.status,year:Number(row.year),month:row.m,direction:['EXPORT','PRODUCTION','EMISSION','DISTRIBUTION'].includes(type)?'OUT':'IN',
      note:row.code+'.csv #'+row.line};
  }
  return {accepted,rate,compatible,display,groupRows,amount,csvRow};
})();
