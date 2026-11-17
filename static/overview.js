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
