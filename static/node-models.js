(() => {
'use strict';
if(!window.THREE)return;
const blue=0x93b2bb,steel=0x607d89,roof=0x577983,brass=0xd3a66d;
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

let renderer;
try {renderer=new THREE.WebGLRenderer({alpha:true,antialias:true,preserveDrawingBuffer:true});}
catch{return;}
renderer.setSize(240,200);
renderer.setPixelRatio(1);
renderer.outputEncoding=THREE.sRGBEncoding;
const images=new Map();
function image(kind){
 if(images.has(kind))return images.get(kind);
 const scene=new THREE.Scene();
 scene.add(new THREE.HemisphereLight(0xf1faff,0x5b7185,1.2));
 const key=new THREE.DirectionalLight(0xfff1d5,1.15);key.position.set(-5,9,6);scene.add(key);
 const p=new THREE.Group();scene.add(p);
 block(p,0,.04,0,3.8,.12,2.65,0x45616a);
 if(kind==='coal'){
  for(const [x,z,r] of [[-.8,0,.55],[.05,.25,.65],[.9,-.25,.5]])
   shape(p,new THREE.DodecahedronGeometry(r,0),0x59636b,x,.5,z);
 }else if(kind==='gas'||kind==='oil'||kind==='other') facility(p,kind==='oil'?0:kind==='gas'?1:3);
 else if(kind==='refining'||kind==='hub')facility(p,2);
 else if(kind==='transport'){
  block(p,-.2,.57,0,1.75,.8,.8,0x93b2bb);block(p,1,.44,0,.65,.55,.8,brass);
  for(const x of [-.7,.8])for(const z of [-.47,.47])shape(p,new THREE.CylinderGeometry(.22,.22,.14,10),0x263e47,x,.25,z).rotation.x=Math.PI/2;
 }else if(kind==='cooking'){
  block(p,0,.6,0,1.65,1.1,1.4,blue);
  shape(p,new THREE.ConeGeometry(1.38,.7,4),roof,0,1.5,0).rotation.y=Math.PI/4;
  block(p,0,.45,.73,.35,.7,.05,brass);
 }else if(kind==='co2'){
  for(const [x,y,r] of [[-.7,1,.35],[0,1.5,.4],[.7,.9,.3]]){
   shape(p,new THREE.IcosahedronGeometry(r,1),0xbacbd1,x,y,0);
   beam(p,[x,.1,0],[x,y-r,0],.025,steel);
  }
 }else facility(p,4);
 const camera=new THREE.OrthographicCamera(-2.7,2.7,2.25,-2.25,.1,100);
 camera.position.set(6,5,8);camera.lookAt(0,1,0);
 renderer.render(scene,camera);
 const url=renderer.domElement.toDataURL('image/png');images.set(kind,url);
 scene.traverse(o=>{o.geometry?.dispose();o.material?.dispose();});
 return url;
}
function replace(el,kind){
 if(el.dataset.model===kind)return;
 const img=document.createElement('img');img.src=image(kind);img.alt='';img.draggable=false;
 el.replaceChildren(img);el.dataset.model=kind;
}
function refresh(){
 for(const kind of ['coal','gas','oil']){const el=document.querySelector('.fuel-'+kind+' .iso-block');if(el)replace(el,kind);}
 const hub=document.querySelector('.annual-hub .iso-block');if(hub)replace(hub,'hub');
 for(const el of document.querySelectorAll('.annual-node .iso-block'))replace(el,el.parentElement.dataset.node);
}
refresh();
const nodes=document.querySelector('#annual-nodes');
if(nodes)new MutationObserver(refresh).observe(nodes,{childList:true});
})();
