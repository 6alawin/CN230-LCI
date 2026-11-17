(() => {
const host=document.getElementById('workspace-sidebar');
if(!host)return;
host.className='workspace-sidebar';
const active=location.pathname.replace(/\/$/,'')||'/';
host.innerHTML='<div class="workspace-brand"><div class="workspace-mark">LCI</div><div>CN230 LCI<small>Energy & resource data</small></div></div><nav aria-label="เมนูหลัก"></nav><div class="workspace-note"><div><span id="side-dot"></span><span id="side-health">Life Cycle Inventory</span></div><p>เชื่อมข้อมูลพลังงาน<br>กับแหล่งอ้างอิงที่ตรวจสอบได้</p></div>';
const nav=host.querySelector('nav');
for(const [url,label] of [['/','Overview'],['/search','Search'],['/query','Query']]){
 const a=document.createElement('a');a.href=url;a.textContent=label;a.className='workspace-nav';
 if(url===active){a.classList.add('active');a.setAttribute('aria-current','page');}nav.append(a);
}
})();
