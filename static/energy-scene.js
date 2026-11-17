/* CN230 • Energy flow scene, Three.js r128. Quantity strings come from the dashboard. */
(() => {
  'use strict';
  const STAGES = {
    en: ['Supply', 'Midstream', 'Refining & processing', 'Distribution', 'End use'],
    th: ['จัดหาพลังงาน', 'กลางน้ำ', 'กลั่นและแปรรูป', 'กระจายพลังงาน', 'ใช้ปลายทาง']
  };
  const FUEL = {
    oil: ['Oil', 'น้ำมัน', 0x966246], gas: ['Natural gas', 'ก๊าซธรรมชาติ', 0x64bbd8],
    lpg: ['LPG', 'LPG', 0xb28cdd], coal: ['Coal', 'ถ่านหิน', 0x637281],
    bio: ['Biofuel', 'เชื้อเพลิงชีวภาพ', 0x80bd80], co2: ['CO₂', 'CO₂', 0xb7c5cf]
  };
  const REFINED = 0xe4a04d;
  const centers = [[-10.5, 1.7], [-5.1, -1.3], [0, 1.1], [5.1,-1.3], [10.5,1.7]];
  const blue = 0x93b2bb, steel = 0x607d89, roof = 0x577983, brass = 0xd3a66d;
  const style = `
    #energy-scene {--scene-ink:#e3eff1;--scene-muted:#b0c4cd;color:var(--scene-ink);min-width:0}
    #energy-scene .es-plot {height:clamp(330px,40vw,510px);position:relative;border-radius:14px;background:radial-gradient(ellipse at 48% 38%,#23414a,#111e2a 75%);overflow:hidden}
    #energy-scene .es-plot canvas {position:absolute;inset:0;display:block;width:100%;height:100%;touch-action:none;cursor:grab}
    #energy-scene .es-plot canvas:active{cursor:grabbing}
    #energy-scene .es-zone {position:absolute;pointer-events:auto;white-space:nowrap;border:1px solid #375562;background:#112631ef;color:#e3eff1;border-radius:20px;padding:3px 8px;transform:translate(-50%,-50%);font-size:clamp(10px,1vw,13px)}
    #energy-scene .es-zone[aria-pressed="true"] {border-color:#a7ebd1}
    #energy-scene .es-tip {position:absolute;z-index:3;max-width:min(340px,85%);max-height:48%;overflow:hidden;pointer-events:none;white-space:pre-line;color:#e6eff3;background:#071b28f5;border:1px solid #70bca3;border-radius:8px;padding:9px 12px;font-size:12px;line-height:1.6}
    #energy-scene .es-hint,#energy-scene .es-legend{font-size:12px;line-height:1.65;margin:8px 0;color:inherit}
    #energy-scene .es-list {display:grid;grid-template-columns:repeat(auto-fit,minmax(min(225px,100%),1fr));gap:7px}
    #energy-scene .es-record {text-align:start;display:grid;gap:4px;padding:9px 12px;background:#142833;color:#cddfe5;border:1px solid #344c59;border-inline-start:4px solid var(--fuel);border-radius:7px;min-width:0;overflow-wrap:anywhere}
    #energy-scene .es-record strong {font-weight:600;color:#f1f5f6}
    #energy-scene .es-record small {font-size:11px;color:#a5bec7}
    #energy-scene .es-record[aria-pressed=true]{border-color:#85cbb1}
    #energy-scene .es-toolbar {display:flex;gap:6px;align-items:center;flex-wrap:wrap;margin:12px 0}
    #energy-scene .es-swatch{display:inline-block;width:.7em;height:.7em;border-radius:50%;margin-inline:9px 4px}
    #energy-scene [hidden]{display:none!important}
    @media(prefers-color-scheme:light){#energy-scene .es-legend,#energy-scene .es-hint{color:inherit}}
  `;
  const element = (tag, cls, text) => {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined) e.textContent = text;
    return e;
  };
  const cssColor = c => '#' + c.toString(16).padStart(6,'0');
  function colorFor(group) {
    // น้ำมันสำเร็จรูปใช้สีส้มตาม SRC และผลิตภัณฑ์ที่จำแนกในต้นทาง
    if (group.fuel === 'oil' && (['SRC-05','SRC-06','SRC-07','SRC-08','SRC-22'].includes(group.source) ||
        /diesel|fuel oil|gasoline|kerosene/i.test(group.flow || ''))) return REFINED;
    return (FUEL[group.fuel] || ['', '', blue])[2];
  }
  const mobile = matchMedia('(max-width: 760px)');
  let root, plot, stageBar, records, nav, legend, hint, tip, zoneLabels=[];
  let scene, camera, renderer, modelLayer, ray, hits=[], marks=[], failed=false;
  let yaw=.18, pitch=.67, zoom=1, panX=0,panZ=0, frame=0, observer;
  let groups=[], lang='th', activeStage=0, selected=null, page=0, activeBucket=null, onSelect;
  const label = (th,en) => lang==='th'?th:en;
  const groupText = g => [g.label, g.flow, g.process].filter((v,i,a)=>v && a.indexOf(v)===i).join(' · ');
  const describe = g => [groupText(g),g.amount,[g.period,g.source,g.status].filter(Boolean).join(' · ')].filter(Boolean).join('\n');
  function mount() {
    root=document.getElementById('energy-scene');
    if (!root) return false;
    const css=element('style');css.textContent=style;
    plot=element('div','es-plot');
    hint=element('p','es-hint');
    legend=element('div','es-legend');
    stageBar=element('div','es-toolbar');
    records=element('div','es-list');
    nav=element('div','es-toolbar');
    tip=element('div','es-tip');tip.setAttribute('role','tooltip');tip.hidden=true;
    plot.append(tip);
    root.replaceChildren(css,plot,hint,legend,stageBar,records,nav);
    observer=new ResizeObserver(redraw);observer.observe(plot);
    mobile.addEventListener('change',()=>render(groups,{lang,selected,onSelect}));
    return true;
  }
  function mat(color) {
    return new THREE.MeshStandardMaterial({color,roughness:.85,metalness:.12,flatShading:true});
  }
  function shape(parent,geo,color,x,y,z) {
    const mesh=new THREE.Mesh(geo,mat(color));mesh.position.set(x,y,z);parent.add(mesh);return mesh;
  }
  function block(p,x,y,z,w,h,d,c) {return shape(p,new THREE.BoxGeometry(w,h,d),c,x,y,z);}
  function tank(p,x,z,h,r,c=blue) {
    shape(p,new THREE.CylinderGeometry(r,r,h,10),c,x,h/2+.15,z);
    shape(p,new THREE.ConeGeometry(r,.18,10),roof,x,h+.23,z);
  }
  function beam(p,from,to,r,c) {
    const a=new THREE.Vector3(...from),b=new THREE.Vector3(...to),v=b.clone().sub(a);
    const m=shape(p,new THREE.CylinderGeometry(r,r,v.length(),6),c,0,0,0);
    m.position.copy(a.add(b).multiplyScalar(.5));
    m.quaternion.setFromUnitVectors(new THREE.Vector3(0,1,0),v.normalize());
  }
  function facility(p,id) {
    if(id===0){
      // แบบจำลองแท่นผลิตและเรือนำเข้าใช้เป็นสัญลักษณ์ของโซน
      block(p,-.55,.35,0,1.8,.3,1.25,steel);
      for(const x of [-1.2,.1]) for(const z of [-.45,.45])beam(p,[x,.5,z],[-.55,2.65,0],.065,brass);
      block(p,-.55,1.25,0,1.1,.12,.7,steel);
      block(p,1,.34,.7,1.85,.34,.60,roof);
      const prow=shape(p,new THREE.ConeGeometry(.39,.7,4),roof,2.12,.34,.7);prow.rotation.z=-Math.PI/2;
      block(p,.55,.67,.7,.47,.45,.47,blue);
      for(const x of [1,1.45]) block(p,x,.56,.7,.33,.18,.36,brass);
    } else if(id===1){
      tank(p,-.65,0,1.1,.54);tank(p,.65,0,1.1,.54);
      beam(p,[-1.45,.57,.65],[1.5,.57,.65],.12,brass);
      for(const x of [-.65,.65])beam(p,[x,.57,.65],[x,.57,.05],.12,brass);
    } else if(id===2){
      block(p,-.6,.56,0,1.35,.85,1.02,steel);
      for(const [x,h] of [[-.72,2.6],[.0,2.04],[.72,1.83]]){
        tank(p,x,-.28,h,.2,blue);
        for(let y=.6;y<h;y+=.5)shape(p,new THREE.CylinderGeometry(.25,.25,.08,10),brass,x,y,-.28);
      }
      tank(p,.95,.57,.62,.43);
    } else if(id===3){
      for(const [x,z] of [[-.64,-.26],[.55,-.26],[0,.62]]) tank(p,x,z,.94,.47);
      beam(p,[-1.4,.36,.98],[1.3,.36,.98],.09,brass);
    } else {
      block(p,-.48,.62,0,1.48,1,1.1,blue);tank(p,.63,-.42,2.0,.18,steel);
      for(const x of [-.87,-.45,-.03])block(p,x,.76,.57,.19,.26,.05,brass);
      block(p,.96,.45,.4,.82,.62,.78,steel);
      const r=shape(p,new THREE.ConeGeometry(.75,.42,4),roof,.96,.96,.4);r.rotation.y=Math.PI/4;
    }
  }
  function dispose(layer) {
    if(!layer)return;
    layer.traverse(o=>{o.geometry?.dispose(); if(o.material) o.material.dispose();});
    if (layer.parent) layer.parent.remove(layer);
  }
  function init3d() {
    if(renderer)return true;
    if(failed||!window.THREE)return false;
    try {
      renderer=new THREE.WebGLRenderer({antialias:true,alpha:true,powerPreference:'low-power'});
      renderer.setPixelRatio(Math.min(devicePixelRatio||1,2));
      renderer.outputEncoding=THREE.sRGBEncoding;
      scene=new THREE.Scene();camera=new THREE.OrthographicCamera(-15,15,8,-8,.1,150);
      scene.add(new THREE.HemisphereLight(0xf1faff,0x5b7185,1.15));
      const key=new THREE.DirectionalLight(0xfff1d5,1.12);key.position.set(-8,18,10);scene.add(key);
      ray=new THREE.Raycaster(); plot.prepend(renderer.domElement);
      controls(renderer.domElement);
      renderer.domElement.addEventListener('webglcontextlost',e=>{
        e.preventDefault();failed=true; renderer.dispose();renderer=null;
        render(groups,{lang,selected,onSelect});
      });
      return true;
    } catch {failed=true;renderer=null;return false;}
  }
  function addLine(layer, points, conceptual) {
    const geometry=new THREE.BufferGeometry().setFromPoints(points.map(a=>new THREE.Vector3(...a)));
    const material=conceptual? new THREE.LineDashedMaterial({color:0x607681,dashSize:.23,gapSize:.19}):
      new THREE.LineBasicMaterial({color:0x718990});
    const line=new THREE.Line(geometry,material);
    if(conceptual)line.computeLineDistances();
    layer.add(line);return line;
  }
  function build() {
    dispose(modelLayer);modelLayer=new THREE.Group();scene.add(modelLayer);hits=[];marks=[];
    for(const label of zoneLabels)label.remove();zoneLabels=[];
    const zoneList=[];
    for(let stage=0;stage<5;stage++){
      const [x,z]=centers[stage], list=groups.filter(g=>g.stage===stage);
      if(!list.length)continue;
      zoneList.push(stage);
      const area=new THREE.Group();area.position.set(x,0,z);modelLayer.add(area);
      const base=block(area,0,-.16,0,4.5,.28,4.0,0x314951);
      const model=new THREE.Group();area.add(model);facility(model,stage);
      model.traverse(o=>{if(o.isMesh){o.userData.stage=stage;hits.push(o);}});
      base.userData.stage=stage;hits.push(base);
      // เส้นทึบแสดงการจัดรายการตามโซน เส้นประระหว่างโซนเป็นเพียงแนวคิด
      const buckets=new Map();
      for(const g of list){
        const key=g.fuel+'|'+colorFor(g);
        if(!buckets.has(key))buckets.set(key,[]);
        buckets.get(key).push(g);
      }
      let i=0;
      for(const [key,items] of buckets){
        const px=buckets.size===1?0:-1.78+i*3.56/(buckets.size-1); i++;
        const stem=addLine(area,[[0,.13,.65],[px,.15,1.62]],false);
        const node=shape(area,new THREE.CylinderGeometry(.24,.33,.25,8),colorFor(items[0]),px,.29,1.62);
        node.userData={stage,items,key};hits.push(node);marks.push({node,stem,items});
      }
      const b=element('button','es-zone',STAGES[lang][stage]);b.type='button';b.dataset.stage=String(stage);b.onclick=()=>choose(stage,null);
      plot.append(b);zoneLabels.push(b);
    }
    for(let i=1;i<zoneList.length;i++){
      const [x,z]=centers[zoneList[i-1]], [nx,nz]=centers[zoneList[i]];
      addLine(modelLayer,[[x+2.25,-.05,z],[nx-2.25,-.05,nz]],true);
    }
  }
  function redraw() {
    if(frame||!renderer||plot.hidden)return;
    frame=requestAnimationFrame(()=>{
      frame=0;if(!renderer||plot.hidden)return;
      const w=plot.clientWidth,h=plot.clientHeight;
      if (!w||!h)return;
      renderer.setSize(w,h,false);
      const ratio=w/h,span=Math.max(6.1,14.9/ratio)/zoom;
      camera.left=-span*ratio;camera.right=span*ratio;camera.top=span;camera.bottom=-span;
      camera.position.set(panX+38*Math.cos(pitch)*Math.sin(yaw),38*Math.sin(pitch),panZ+38*Math.cos(pitch)*Math.cos(yaw));
      camera.lookAt(panX,.32,panZ);camera.updateProjectionMatrix();camera.updateMatrixWorld();
      for(const b of zoneLabels){
        const stage=Number(b.dataset.stage),[x,z]=centers[stage];
        const p=new THREE.Vector3(x,3.25,z).project(camera);
        b.style.left=(p.x+1)*50+'%';b.style.top=(1-p.y)*50+'%';b.setAttribute('aria-pressed',String(stage===activeStage));
      }
      for(const {node,stem,items} of marks){
        const hot=items.some(g=>g.id===selected);
        node.material.emissive.setHex(hot?0x5b9b80:0);stem.material.color.setHex(hot?0xc7ffde:0x718990);
      }
      renderer.render(scene,camera);
    });
  }
  function pick(canvas,e) {
    const rect=canvas.getBoundingClientRect();
    ray.setFromCamera({x:2*(e.clientX-rect.left)/rect.width-1,y:1-2*(e.clientY-rect.top)/rect.height},camera);
    return ray.intersectObjects(hits,false)[0]?.object.userData;
  }
  function controls(canvas) {
    let start=null;
    canvas.onpointerdown=e=>{
      start={x:e.clientX,y:e.clientY,yaw,pitch,panX,panZ,pan:e.shiftKey||e.button===2,drag:false};
      canvas.setPointerCapture(e.pointerId);
    };
    canvas.oncontextmenu=e=>e.preventDefault();
    canvas.onpointermove=e=>{
      if(start) {
        const dx=e.clientX-start.x,dy=e.clientY-start.y;
        if(Math.abs(dx)+Math.abs(dy)>4) start.drag=true;
        if(start.drag){
          if(start.pan){
            const scale=30/(canvas.clientWidth*zoom);
            panX=start.panX-scale*(dx*Math.cos(yaw)+dy*Math.sin(yaw));panZ=start.panZ+scale*(dx*Math.sin(yaw)-dy*Math.cos(yaw));
          } else {yaw=start.yaw-dx*.008;pitch=Math.max(.26,Math.min(1.28,start.pitch+dy*.006));}
          tip.hidden=true;redraw();
        }
        return;
      }
      const hit=pick(canvas,e);
      if(!hit){tip.hidden=true;return;}
      const list=hit.items||groups.filter(g=>g.stage===hit.stage);
      tip.textContent=STAGES[lang][hit.stage]+'\n'+list.slice(0,2).map(describe).join('\n')+(list.length>2?'\n+'+(list.length-2)+' '+label('รายการ','records'):'');
      tip.hidden=false;
      const rect=plot.getBoundingClientRect();
      tip.style.left=Math.max(0,Math.min(rect.width-tip.offsetWidth,e.clientX-rect.left+12))+'px';
      tip.style.top=Math.max(0,Math.min(rect.height-tip.offsetHeight,e.clientY-rect.top+12))+'px';
    };
    canvas.onpointerup=e=>{
      if(start && !start.drag){
        const hit=pick(canvas,e);
        if(hit) choose(hit.stage,hit.items||null);
      }
      start=null;
    };
    canvas.onpointercancel=()=>{start=null};canvas.onpointerleave=()=>{tip.hidden=true};
    canvas.addEventListener('wheel',e=>{
      e.preventDefault();zoom=Math.min(4,Math.max(.65,zoom*Math.exp(-e.deltaY*.0015)));redraw();
    },{passive:false});
  }
  function choose(stage,items) {
    activeStage=stage;activeBucket=items;page=0;tip.hidden=true;
    const first=(items||groups.filter(g=>g.stage===stage))[0];
    if(first){selected=first.id;onSelect?.(first.id);}
    listing();redraw();
  }
  function listing() {
    stageBar.replaceChildren();records.replaceChildren();nav.replaceChildren();
    if (!groups.length){records.textContent=label('ไม่มีข้อมูลตามเงื่อนไข','No matching records');return;}
    STAGES[lang].forEach((name,i)=>{
      if(!groups.some(g=>g.stage===i))return;
      const button=element('button','',name);button.type='button';button.setAttribute('aria-pressed',String(activeStage===i));
      button.onclick=()=>choose(i,null);stageBar.append(button);
    });
    const list=activeBucket || groups.filter(g=>g.stage===activeStage);
    const size=6;page=Math.max(0,Math.min(page,Math.ceil(list.length/size)-1));
    for(const g of list.slice(page*size,(page+1)*size)){
      const b=element('button','es-record');b.type='button';b.title=describe(g);
      b.style.setProperty('--fuel',cssColor(colorFor(g)));
      b.setAttribute('aria-pressed',String(g.id===selected));
      b.append(element('strong','',groupText(g)),element('span','',g.amount||'—'),element('small','',[g.period,g.source,g.status].filter(Boolean).join(' · ')));
      b.onclick=()=>{selected=g.id;onSelect?.(g.id);listing();redraw();};records.append(b);
    }
    if(list.length>size){
      const prev=element('button','',label('ก่อนหน้า','Previous')),next=element('button','',label('ถัดไป','Next'));
      prev.type=next.type='button';prev.disabled=page===0;next.disabled=(page+1)*size>=list.length;
      prev.onclick=()=>{page--;listing()};next.onclick=()=>{page++;listing()};
      nav.append(prev,element('span','',(page+1)+' / '+Math.ceil(list.length/size)),next);
    }
  }
  function render(incoming,options={}) {
    if(!root && !mount())return;
    const nextLang=options.lang==='en'?'en':'th';
    const changed=incoming!==groups||lang!==nextLang;
    if(changed){activeBucket=null;page=0;tip.hidden=true;}
    groups=incoming;lang=nextLang;onSelect=options.onSelect;selected=options.selected??null;
    const found=groups.find(g=>g.id===selected);
    if(found)activeStage=found.stage;
    else if(!groups.some(g=>g.stage===activeStage))activeStage=groups[0]?.stage??0;
    plot.hidden=mobile.matches||!groups.length||!init3d();
    if (!plot.hidden && (changed||!modelLayer))build();
    if(plot.hidden && changed && modelLayer){dispose(modelLayer);modelLayer=null;}
    hint.textContent=plot.hidden?label('เลือกระยะและรายการเพื่อดูหลักฐาน','Choose a stage and record to inspect the evidence'):
      label('ลากเพื่อหมุน · Shift + ลากเพื่อเลื่อน · เลื่อนล้อเพื่อซูม','Drag to orbit · Shift + drag to pan · Scroll to zoom');
    legend.replaceChildren();
    for(const [en,th,color] of [...Object.values(FUEL),['Refined oil','น้ำมันสำเร็จรูป',REFINED]]){
      const dot=element('i','es-swatch');dot.style.background=cssColor(color);legend.append(dot,lang==='en'?en:th);
    }
    legend.append(element('div','',label('— รายการในขั้นที่ระบุโดยข้อมูล  ┄ เส้นทางเชิงแนวคิดระหว่างขั้น · เส้นกว้างคงที่ทุกหน่วย','— Records mapped to a stage  ┄ Conceptual links between stages · Fixed width across units')));
    listing();redraw();
  }
  window.energyScene={render};
})();
