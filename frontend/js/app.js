// IntelliTwin App — premium studio, preserves all backend contracts
const API = {
  parse: '/api/parse',
  generate: '/api/generate',
  validate: '/api/validate',
  cost: '/api/cost',
  health: '/api/health',
  modelStatus: '/api/model/status',
  rates: '/api/rates'
};

let lastLayout = null;
let lastParsed = null;
let lastCompliance = null;
let lastCost = null;
let lastGCN = null;
let planZoom = 1;

// Core elements (preserved)
const reqInput = document.getElementById('reqInput');
const generateBtn = document.getElementById('generateBtn');
const resetBtn = document.getElementById('resetBtn');
const rateProfile = document.getElementById('rateProfile');
const planSvg = document.getElementById('planSvg');
const planContainer = document.getElementById('planContainer');
const planEmpty = document.getElementById('planEmpty');
const planDims = document.getElementById('planDims');
const threeCanvas = document.getElementById('threeCanvas');
const twinEmpty = document.getElementById('twinEmpty');
const twinOverlay = document.getElementById('twinOverlay');
const twinBadge = document.getElementById('twinBadge');
const complianceStrip = document.getElementById('complianceStrip');
const complianceBadge = document.getElementById('complianceBadge');
const complianceScore = document.getElementById('complianceScore');
const complianceNote = document.getElementById('complianceNote');
const reportGrid = document.getElementById('reportGrid');
const parsePreview = document.getElementById('parsePreview');
const errorBox = document.getElementById('errorBox');
const roomDetails = document.getElementById('roomDetails');
const toggleFurniture = document.getElementById('toggleFurniture');
const toggleLighting = document.getElementById('toggleLighting');
const togglePlumbing = document.getElementById('togglePlumbing');
const toggleFurniture3D = document.getElementById('toggleFurniture3D');
const copyPlanBtn = document.getElementById('copyPlanBtn');

// Studio extras
const cfgBedrooms = document.getElementById('cfgBedrooms');
const cfgBathrooms = document.getElementById('cfgBathrooms');
const cfgBalconies = document.getElementById('cfgBalconies');
const cfgArea = document.getElementById('cfgArea');
const cfgStyle = document.getElementById('cfgStyle');
const cfgKitchen = document.getElementById('cfgKitchen');
const cfgDirection = document.getElementById('cfgDirection');
const cfgFloors = document.getElementById('cfgFloors');
const modelPill = document.getElementById('modelPill');
const studioStatusPill = document.getElementById('studioStatusPill');
const projectName = document.getElementById('projectName');
const projectSub = document.getElementById('projectSub');
const footGen = document.getElementById('footGen');
const footWarn = document.getElementById('footWarn');
const inspectorRoom = document.getElementById('inspectorRoom');
const inspectorRoomEmpty = document.getElementById('inspectorRoomEmpty');
const inspectorValidate = document.getElementById('inspectorValidate');
const inspectorCost = document.getElementById('inspectorCost');
const inspectorSystems = document.getElementById('inspectorSystems');
const inspectorTitle = document.getElementById('inspectorTitle');
const inspectorSub = document.getElementById('inspectorSub');
const planZoomIn = document.getElementById('planZoomIn');
const planZoomOut = document.getElementById('planZoomOut');
const planZoomReset = document.getElementById('planZoomReset');
const btnSavePng = document.getElementById('btnSavePng');
const exportJsonBtn = document.getElementById('exportJsonBtn');
const inspectorExportBtn = document.getElementById('inspectorExportBtn');
const inspectorPrintBtn = document.getElementById('inspectorPrintBtn');
const planEmptyGenerate = document.getElementById('planEmptyGenerate');
const resetBtnHeader = document.getElementById('resetBtnHeader');
const helpBtn = document.getElementById('helpBtn');

// Studio tabs (Plan / Twin / Report)
document.querySelectorAll('.tab').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.viewer-panel').forEach(p => p.classList.remove('active'));
    btn.classList.add('active');
    const tab = btn.dataset.tab;
    const panel = document.getElementById('panel-' + tab);
    if (panel) panel.classList.add('active');
    if (tab === 'twin' && window.ThreeViewer) {
      setTimeout(() => window.ThreeViewer.buildFromLayout && lastLayout && window.ThreeViewer.buildFromLayout(lastLayout, { furniture: toggleFurniture3D?.checked ?? true }), 120);
      if (lastLayout && window.ThreeViewer) {
        // ensure resize
        setTimeout(() => window.dispatchEvent(new Event('resize')), 160);
      }
    }
    if (tab === 'plan' && lastLayout) render2D();
  });
});

// Inspector tabs
document.querySelectorAll('.itab').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.itab').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.itab-panel').forEach(p => p.classList.remove('active'));
    btn.classList.add('active');
    const id = btn.dataset.itab;
    const panel = document.getElementById('itab-' + id);
    if (panel) panel.classList.add('active');
  });
});

// Theme toggle
const themeToggle = document.getElementById('themeToggle');
function applyTheme(t) {
  document.documentElement.setAttribute('data-theme', t);
  localStorage.setItem('intellitwin-theme', t);
  if (themeToggle) themeToggle.textContent = t === 'dark' ? '☀' : '◐';
}
const savedTheme = localStorage.getItem('intellitwin-theme') || (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
applyTheme(savedTheme);
themeToggle?.addEventListener('click', () => {
  const cur = document.documentElement.getAttribute('data-theme');
  applyTheme(cur === 'dark' ? 'light' : 'dark');
  if (lastLayout) render2D();
});

// Scroll progress + back to top + header shadow
const scrollProg = document.getElementById('scroll-progress');
const btt = document.getElementById('backToTop');
const header = document.getElementById('header');
window.addEventListener('scroll', () => {
  const h = document.documentElement;
  const pct = (h.scrollTop / (h.scrollHeight - h.clientHeight)) * 100;
  if (scrollProg) scrollProg.style.width = pct + '%';
  if (btt) {
    if (h.scrollTop > 380) btt.classList.add('show'); else btt.classList.remove('show');
  }
  if (header) header.style.boxShadow = window.scrollY > 6 ? '0 8px 24px rgba(15,25,48,0.06)' : 'none';
});
btt?.addEventListener('click', () => window.scrollTo({ top: 0, behavior: 'smooth' }));

// Mobile menu
const menuBtn = document.getElementById('menuBtn');
const mobileNav = document.getElementById('mobileNav');
menuBtn?.addEventListener('click', () => {
  const hidden = mobileNav.hasAttribute('hidden');
  if (hidden) mobileNav.removeAttribute('hidden'); else mobileNav.setAttribute('hidden', '');
  menuBtn.setAttribute('aria-expanded', String(hidden));
});

// Cookie banner
const cookieBanner = document.getElementById('cookieBanner');
function checkCookie(){ if (!localStorage.getItem('intellitwin-cookies') && cookieBanner) cookieBanner.removeAttribute('hidden'); }
checkCookie();
document.getElementById('cookieAccept')?.addEventListener('click', () => {
  localStorage.setItem('intellitwin-cookies', 'accepted');
  cookieBanner?.setAttribute('hidden','');
  toast('Preferences saved — only essential storage used.');
});
document.getElementById('cookieDecline')?.addEventListener('click', () => {
  localStorage.setItem('intellitwin-cookies', 'declined');
  cookieBanner?.setAttribute('hidden','');
  toast('Preferences saved.');
});
document.getElementById('cookiePrefs')?.addEventListener('click', e => { e.preventDefault(); cookieBanner?.removeAttribute('hidden'); });
document.getElementById('cookieLearn')?.addEventListener('click', e => { e.preventDefault(); toast('We store theme and session only. No tracking.'); });

// Toast
const toastEl = document.getElementById('toast');
let toastTimer=null;
function toast(msg, ms=3400){
  if(!toastEl) return;
  toastEl.textContent=msg;
  toastEl.removeAttribute('hidden');
  clearTimeout(toastTimer);
  toastTimer=setTimeout(()=>toastEl.setAttribute('hidden',''), ms);
}

// Presets
const presets={
  bhk3:"I want a modern 3BHK house with 1500 square feet of built-up area, three bedrooms, two bathrooms, an open kitchen, a spacious living room, a balcony, furniture placement, proper lighting, plumbing connections, and an east-facing main entrance.",
  bhk2:"2BHK minimal house, 1100 sqft, 2 bedrooms 2 bathrooms, open kitchen, living and dining combined, one balcony, north facing entrance, furniture and lighting",
  bhk4:"Luxury 4BHK villa 2200 sqft, 4 bedrooms, 3 bathrooms, open kitchen, dining, living, 2 balconies, south facing, modern style, furniture lighting plumbing",
  studio:"1BHK compact 650 sqft, 1 bedroom, 1 bathroom, open kitchen, living hall, east facing, minimal furniture"
};
document.querySelectorAll('.preset').forEach(b=>{
  b.addEventListener('click',()=>{
    const k=b.dataset.preset;
    if(reqInput) reqInput.value=presets[k]||'';
    syncConfigFromText(presets[k]||'');
    reqInput?.focus();
    toast('Preset loaded — adjust config or hit Generate');
  });
});
document.getElementById('demoBtn')?.addEventListener('click', e=>{
  e.preventDefault();
  if(reqInput) reqInput.value=presets.bhk3;
  syncConfigFromText(presets.bhk3);
  document.getElementById('app')?.scrollIntoView({behavior:'smooth'});
});
planEmptyGenerate?.addEventListener('click', ()=>{
  if(reqInput) reqInput.value=presets.bhk3;
  syncConfigFromText(presets.bhk3);
  doGenerate();
});

// Config sync: when text changes, try to infer via quick parse (without API) for immediate feedback; API parse will correct
function syncConfigFromText(text){
  // lightweight regex sync for instant UI; real parse via API debounced below will overwrite precisely
  const low=(text||'').toLowerCase();
  const bhk = (low.match(/(\d)\s*bhk/)||[])[1];
  if(bhk && cfgBedrooms) cfgBedrooms.value=bhk;
  const area = (low.match(/(\d{3,5})\s*(sqft|sq\. ft|square feet)/)||[])[1];
  if(area && cfgArea) cfgArea.value=area;
  if(/north/.test(low) && cfgDirection) cfgDirection.value = low.includes('north') && low.includes('east') ? 'north_east' : low.includes('north') && low.includes('west') ? 'north_west' : 'north';
  else if(/south/.test(low) && cfgDirection) cfgDirection.value = low.includes('south') && low.includes('east') ? 'south_east' : low.includes('south') && low.includes('west') ? 'south_west' : 'south';
  else if(/west/.test(low) && cfgDirection) cfgDirection.value='west';
  else if(/east/.test(low) && cfgDirection) cfgDirection.value='east';
  if(/traditional/.test(low) && cfgStyle) cfgStyle.value='traditional';
  else if(/minimal/.test(low) && cfgStyle) cfgStyle.value='minimal';
  else if(/luxury/.test(low) && cfgStyle) cfgStyle.value='luxury';
  else if(/contemporary/.test(low) && cfgStyle) cfgStyle.value='contemporary';
  else if(/classic/.test(low) && cfgStyle) cfgStyle.value='classic';
  else if(cfgStyle) cfgStyle.value='modern';
  if(/closed kitchen/.test(low) && cfgKitchen) cfgKitchen.value='closed';
  else if(cfgKitchen) cfgKitchen.value='open';
}
function syncConfigFromParsed(p){
  if(!p) return;
  if(cfgBedrooms) cfgBedrooms.value=p.bedrooms;
  if(cfgBathrooms) cfgBathrooms.value=p.bathrooms;
  if(cfgBalconies) cfgBalconies.value=p.balconies ?? 0;
  if(cfgArea) cfgArea.value=Math.round(p.total_area_sqft);
  if(cfgStyle) cfgStyle.value=p.style || 'modern';
  if(cfgKitchen) cfgKitchen.value=p.kitchen_type || 'open';
  if(cfgDirection) cfgDirection.value=p.main_entrance_direction || 'east';
  if(cfgFloors) cfgFloors.value=p.floors || 1;
}
function buildParsedOverride(text){
  // If any cfg differs from lastParsed, build override; otherwise null
  if(!lastParsed) {
    // if no lastParsed, use cfg values as override only if user touched configs after text change
    // We treat cfg as source after first parse — so build from cfg
    try{
      const o={
        original_text: text,
        bedrooms: parseInt(cfgBedrooms?.value || 3,10),
        bathrooms: parseInt(cfgBathrooms?.value || 2,10),
        balconies: parseInt(cfgBalconies?.value || 1,10),
        kitchens: 1,
        living_rooms: 1,
        dining_rooms: (parseInt(cfgBedrooms?.value||3,10) >=3 ? 1:0),
        total_area_sqft: parseFloat(cfgArea?.value || 1500),
        kitchen_type: cfgKitchen?.value || 'open',
        style: cfgStyle?.value || 'modern',
        floors: parseInt(cfgFloors?.value||1,10),
        main_entrance_direction: cfgDirection?.value||'east',
        wants_furniture: true, wants_lighting:true, wants_plumbing:true,
        explicit:{ bedrooms:true, bathrooms:true, area:true, direction:true, balcony:true, kitchen_type:true },
        warnings:[], inferred_defaults:{area:false,direction:false}
      };
      // Only use override if cfg values are not default inferred? For now return o only if text parse would differ
      // Compare with quick text parse? Simpler: if cfg values were manually edited (we detect via sync), send override
      // We will send override whenever cfg fields are not empty — backend will prefer parsed override when provided
      // To avoid overriding when user hasn't touched cfg, we check if o matches lastParsed-ish: if any field differs, send
      return o;
    }catch{ return null; }
  }
  const curr={
    bedrooms: parseInt(cfgBedrooms?.value||lastParsed.bedrooms,10),
    bathrooms: parseInt(cfgBathrooms?.value||lastParsed.bathrooms,10),
    balconies: parseInt(cfgBalconies?.value||lastParsed.balconies||0,10),
    total_area_sqft: parseFloat(cfgArea?.value||lastParsed.total_area_sqft),
    style: cfgStyle?.value||lastParsed.style,
    kitchen_type: cfgKitchen?.value||lastParsed.kitchen_type,
    main_entrance_direction: cfgDirection?.value||lastParsed.main_entrance_direction,
    floors: parseInt(cfgFloors?.value||lastParsed.floors||1,10)
  };
  const differs = curr.bedrooms!==lastParsed.bedrooms || curr.bathrooms!==lastParsed.bathrooms || curr.balconies!==(lastParsed.balconies||0) || Math.abs(curr.total_area_sqft-lastParsed.total_area_sqft)>1 || curr.style!==lastParsed.style || curr.kitchen_type!==lastParsed.kitchen_type || curr.main_entrance_direction!==lastParsed.main_entrance_direction || curr.floors!==(lastParsed.floors||1);
  if(!differs) return null;
  return {
    original_text: text,
    bedrooms: curr.bedrooms, bathrooms: curr.bathrooms, balconies: curr.balconies, kitchens:1, living_rooms:1, dining_rooms: lastParsed.dining_rooms||0,
    total_area_sqft: curr.total_area_sqft, kitchen_type: curr.kitchen_type, style: curr.style, floors: curr.floors,
    main_entrance_direction: curr.main_entrance_direction, wants_furniture:true, wants_lighting:true, wants_plumbing:true,
    explicit:{ bedrooms:true, bathrooms:true, area:true, direction:true, balcony:true, kitchen_type:true },
    warnings:[], inferred_defaults:{area:false,direction:false}
  };
}

// Clipboard
copyPlanBtn?.addEventListener('click', async ()=>{
  if(!lastLayout){ toast('No layout to copy'); return; }
  try{ await navigator.clipboard.writeText(JSON.stringify(lastLayout,null,2)); toast('Layout JSON copied'); }
  catch{ toast('Copy failed — see console'); console.log(lastLayout); }
});
btnSavePng?.addEventListener('click', ()=>{
  if(!lastLayout || !planSvg){ toast('No plan to save'); return; }
  const src = new XMLSerializer().serializeToString(planSvg);
  const blob = new Blob([src], {type:'image/svg+xml'});
  const url=URL.createObjectURL(blob);
  const a=document.createElement('a'); a.href=url; a.download=`intellitwin_plan_${Date.now()}.svg`; a.click();
  URL.revokeObjectURL(url);
  toast('SVG downloaded');
});
function downloadReport(){
  if(!lastLayout) { toast('No report yet'); return; }
  const report={ parsed:lastParsed, layout:lastLayout, compliance:lastCompliance, cost:lastCost, gcn:lastGCN, exported_at:new Date().toISOString(), disclaimer:"Approximate planning estimate — not a certified architectural/engineering quotation. Verify with licensed professionals." };
  const blob=new Blob([JSON.stringify(report,null,2)],{type:'application/json'});
  const url=URL.createObjectURL(blob);
  const a=document.createElement('a'); a.href=url; a.download=`intellitwin_report_${Date.now()}.json`; a.click();
  URL.revokeObjectURL(url);
  toast('Report downloaded');
}
window.downloadReport=downloadReport;
exportJsonBtn?.addEventListener('click', downloadReport);
inspectorExportBtn?.addEventListener('click', downloadReport);
inspectorPrintBtn?.addEventListener('click', ()=>window.print());
helpBtn?.addEventListener('click', ()=> document.getElementById('faq')?.scrollIntoView({behavior:'smooth'}));

// Room select — updates both old roomDetails and new inspector
window.onRoomSelect = (room)=>{
  if(roomDetails){
    roomDetails.removeAttribute('hidden');
    roomDetails.innerHTML=`
      <div><strong>${room.label}</strong> <span style="color:#6B7280">(${room.type})</span></div>
      <div>Size: ${room.width} × ${room.height} ft</div>
      <div>Area: ${room.area} sqft (target ${room.target_area||'-'})</div>
      <div>Position: x=${room.x}, y=${room.y}</div>
      <div>Furniture: ${(room.furniture||[]).length} items</div>
      <div>Lighting: ${(room.lighting||[]).length} fixtures</div>
      <div>Plumbing: ${(room.plumbing||[]).length} fixtures</div>
    `;
  }
  if(inspectorRoom && inspectorRoomEmpty){
    inspectorRoomEmpty.setAttribute('hidden','');
    inspectorRoom.removeAttribute('hidden');
    inspectorRoom.innerHTML=`
      <div class="kv"><span>Room</span><span><strong>${room.label}</strong> · ${room.type}</span></div>
      <div class="kv"><span>Dimensions</span><span>${room.width.toFixed(1)} × ${room.height.toFixed(1)} ft</span></div>
      <div class="kv"><span>Area</span><span>${room.area.toFixed(0)} sqft <span style="color:#6B7280">target ${room.target_area||'-'} sqft</span></span></div>
      <div class="kv"><span>Position</span><span>x ${room.x} · y ${room.y}</span></div>
      <div class="kv"><span>Furniture</span><span>${(room.furniture||[]).length ? (room.furniture||[]).map(f=>`${f.type.replace(/_/g,' ')} ${f.width.toFixed(1)}×${f.height.toFixed(1)}`).join('<br>') : 'None'}</span></div>
      <div class="kv"><span>Lighting</span><span>${(room.lighting||[]).length ? (room.lighting||[]).map(l=>l.type).join(', ') : 'None'}</span></div>
      <div class="kv"><span>Plumbing</span><span>${(room.plumbing||[]).length ? (room.plumbing||[]).map(p=>p.type).join(', ') : 'None'}</span></div>
      <div class="kv"><span>Doors / Windows</span><span>${(room.doors||[]).length} doors · ${(room.windows||[]).length} windows</span></div>
    `;
    if(inspectorTitle) inspectorTitle.textContent=room.label;
    if(inspectorSub) inspectorSub.textContent=`${room.type} · ${room.width.toFixed(1)}×${room.height.toFixed(1)} ft`;
    // switch to Room tab
    document.querySelectorAll('.itab').forEach(b=>b.classList.remove('active'));
    document.querySelectorAll('.itab-panel').forEach(p=>p.classList.remove('active'));
    const rt=document.querySelector('.itab[data-itab="room"]');
    const rp=document.getElementById('itab-room');
    if(rt) rt.classList.add('active');
    if(rp) rp.classList.add('active');
  }
};

// Toggles
toggleFurniture?.addEventListener('change', ()=> lastLayout && render2D());
toggleLighting?.addEventListener('change', ()=> lastLayout && render2D());
togglePlumbing?.addEventListener('change', ()=> lastLayout && render2D());
toggleFurniture3D?.addEventListener('change', ()=>{
  if(window.ThreeViewer) window.ThreeViewer.setFurnitureVisible(toggleFurniture3D.checked);
});
document.getElementById('btnToggleWalls')?.addEventListener('click', function(){
  this.dataset.on=this.dataset.on==='1'?'0':'1';
  if(this.dataset.on==='1'){ window.ThreeViewer?.setWallsVisible(false); this.textContent='Show walls'; }
  else { window.ThreeViewer?.setWallsVisible(true); this.textContent='Hide walls'; this.dataset.on='0'; }
});
document.getElementById('btnTopView')?.addEventListener('click', ()=> window.ThreeViewer?.topView());
document.getElementById('btnResetCam')?.addEventListener('click', ()=> window.ThreeViewer?.resetCamera());
document.getElementById('btnDetails')?.addEventListener('click', ()=>{
  document.querySelector('[data-tab="report"]')?.click();
  document.getElementById('reportGrid')?.scrollIntoView({behavior:'smooth', block:'nearest'});
});

// Keyboard shortcuts
window.addEventListener('keydown', e=>{
  if((e.ctrlKey||e.metaKey) && e.key==='Enter'){ e.preventDefault(); doGenerate(); }
  if(e.key.toLowerCase()==='t' && !e.target.matches('input, textarea, select')){ e.preventDefault(); themeToggle?.click(); }
  if(e.key==='Escape'){ mobileNav?.setAttribute('hidden',''); }
  if(e.key.toLowerCase()==='r' && !e.target.matches('input, textarea')){ /* reset camera is in 3D handler */ }
});

// Parse preview debounce + cfg sync
let parseTimer=null;
reqInput?.addEventListener('input', ()=>{
  clearTimeout(parseTimer);
  parseTimer=setTimeout(async ()=>{
    const text=reqInput.value.trim();
    if(text.length<10){ parsePreview?.setAttribute('hidden',''); return; }
    syncConfigFromText(text);
    try{
      const r=await fetch(API.parse,{method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({text})});
      const j=await r.json();
      if(j.parsed){
        lastParsed=j.parsed; // keep for override detection
        syncConfigFromParsed(j.parsed);
        if(parsePreview){
          parsePreview.removeAttribute('hidden');
          const p=j.parsed;
          parsePreview.innerHTML=`
            <h4>Parsed preview</h4>
            <div style="display:grid; grid-template-columns:1fr 1fr; gap:6px; font-size:12.5px">
              <span>Bedrooms: <strong>${p.bedrooms}</strong> ${p.explicit.bedrooms ? '· explicit':'· inferred'}</span>
              <span>Bathrooms: <strong>${p.bathrooms}</strong></span>
              <span>Area: <strong>${Math.round(p.total_area_sqft)} sqft</strong> ${p.inferred_defaults.area ? '· inferred':''}</span>
              <span>Entrance: <strong>${p.main_entrance_direction}</strong></span>
              <span>Kitchen: <strong>${p.kitchen_type}</strong></span>
              <span>Style: <strong>${p.style}</strong></span>
            </div>
            ${p.warnings && p.warnings.length ? `<div style="margin-top:8px; color:#92400E; font-size:11.5px; line-height:1.5">${p.warnings.map(w=>'⚠ '+w).join('<br>')}</div>`:''}
          `;
        }
      }
    }catch{ /* ignore */ }
  }, 500);
});

// Generate flow
async function doGenerate(){
  const text=(reqInput?.value||'').trim();
  if(!text){
    if(errorBox){ errorBox.textContent='Please describe your house requirements.'; errorBox.removeAttribute('hidden'); }
    reqInput?.focus(); return;
  }
  if(errorBox) errorBox.setAttribute('hidden','');
  parsePreview?.setAttribute('hidden','');
  // loading
  if(generateBtn){
    generateBtn.disabled=true;
    const label=generateBtn.querySelector('.btn-label');
    const spinner=generateBtn.querySelector('.spinner');
    if(label) label.textContent='Generating…';
    if(spinner) spinner.removeAttribute('hidden');
  }
  if(footGen) footGen.textContent='Generating — tiling, furniture, GCN scoring…';
  showSkeleton();
  try{
    const profile=rateProfile?.value || 'india_tier2_2025';
    const parsedOverride=buildParsedOverride(text);
    const payload={ text, rate_profile: profile, max_retries:3 };
    if(parsedOverride) payload.parsed=parsedOverride;
    const resp=await fetch(API.generate,{method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)});
    const data=await resp.json();
    if(!resp.ok) throw new Error(data.error||data.detail||'Generation failed');
    lastLayout=data.layout; lastParsed=data.parsed; lastCompliance=data.compliance; lastCost=data.cost; lastGCN=data.gcn;
    // update config to reflect actual parsed (in case backend normalized)
    syncConfigFromParsed(data.parsed);
    renderAll(data);
    toast(`Generated — ${data.compliance.status_label} (${data.compliance.score})`);
    // update studio header
    if(projectName) projectName.textContent=`${data.parsed.bedrooms}BHK · ${Math.round(data.parsed.total_area_sqft)} sqft · ${data.parsed.style}`;
    if(projectSub) projectSub.textContent=`${data.layout.width.toFixed(1)}×${data.layout.height.toFixed(1)} ft · ${data.layout.rooms.length} rooms · ${data.parsed.main_entrance_direction} facing`;
    if(footGen) footGen.textContent=`Generated ${data.layout.rooms.length} rooms · ${data.compliance.status_label} ${data.compliance.score} · GCN ${data.gcn.source}`;
    if(footWarn){
      const hard=(data.compliance.failed||[]).length;
      const soft=(data.compliance.warnings||[]).length;
      footWarn.textContent = hard ? `${hard} hard failures` : soft ? `${soft} warnings · see Check tab` : 'No hard failures';
    }
    document.querySelector('[data-tab="plan"]')?.click();
  }catch(err){
    if(errorBox){ errorBox.textContent=(err&&err.message)?err.message:'Generation failed. Check backend connection.'; errorBox.removeAttribute('hidden'); }
    hideSkeleton();
    if(footGen) footGen.textContent='Generation failed';
    console.error(err);
  }finally{
    if(generateBtn){
      generateBtn.disabled=false;
      const label=generateBtn.querySelector('.btn-label');
      const spinner=generateBtn.querySelector('.spinner');
      if(label) label.textContent='Generate twin';
      if(spinner) spinner.setAttribute('hidden','');
    }
  }
}
generateBtn?.addEventListener('click', doGenerate);
resetBtn?.addEventListener('click', doReset);
resetBtnHeader?.addEventListener('click', doReset);
function doReset(){
  if(reqInput) reqInput.value='';
  parsePreview?.setAttribute('hidden','');
  errorBox?.setAttribute('hidden','');
  roomDetails?.setAttribute('hidden','');
  if(inspectorRoom) { inspectorRoom.setAttribute('hidden',''); inspectorRoom.innerHTML=''; }
  if(inspectorRoomEmpty) inspectorRoomEmpty.removeAttribute('hidden');
  if(inspectorTitle) inspectorTitle.textContent='Inspector';
  if(inspectorSub) inspectorSub.textContent='Select a room';
  lastLayout=null;
  if(planSvg){ planSvg.setAttribute('hidden',''); planSvg.innerHTML=''; }
  planEmpty?.removeAttribute('hidden');
  twinEmpty?.removeAttribute('hidden');
  threeCanvas?.setAttribute('hidden','');
  twinOverlay?.setAttribute('hidden','');
  complianceStrip?.setAttribute('hidden','');
  if(reportGrid) reportGrid.innerHTML=`<div class="empty-state"><div class="empty-icon">◎</div><h4>Report empty</h4><p>Generate a twin to see validation, room schedule, assumptions and the itemized cost sheet.</p></div>`;
  if(planDims) planDims.textContent='';
  if(projectName) projectName.textContent='Untitled · 3BHK House';
  if(projectSub) projectSub.textContent='No generation yet';
  if(footGen) footGen.textContent='Idle — ready';
  if(footWarn) footWarn.textContent='';
  // reset inspector
  if(inspectorValidate) inspectorValidate.innerHTML='<p class="muted">Generate to see compliance checks, GCN score and suggestions.</p>';
  if(inspectorCost) inspectorCost.innerHTML='<p class="muted">Cost appears after generation.</p>';
  if(inspectorSystems) inspectorSystems.innerHTML='<p class="muted">Lighting, plumbing fixtures and routes will be listed here.</p>';
  planZoom=1; if(planSvg) planSvg.style.transform='';
  toast('Reset complete');
}

// Skeleton
function showSkeleton(){
  planEmpty?.setAttribute('hidden','');
  planContainer?.querySelectorAll('.skeleton').forEach(e=>e.remove());
  const sk=document.createElement('div'); sk.className='skeleton'; sk.style.cssText='width:100%; height:380px; border-radius:12px;';
  planContainer?.appendChild(sk);
  twinEmpty?.setAttribute('hidden','');
}
function hideSkeleton(){ planContainer?.querySelectorAll('.skeleton').forEach(e=>e.remove()); }

// Zoom
planZoomIn?.addEventListener('click', ()=>{
  planZoom=Math.min(2.4, planZoom+0.15);
  if(planSvg) planSvg.style.transform=`scale(${planZoom})`;
  planContainer.style.overflow='auto';
});
planZoomOut?.addEventListener('click', ()=>{
  planZoom=Math.max(0.6, planZoom-0.15);
  if(planSvg) planSvg.style.transform=`scale(${planZoom})`;
});
planZoomReset?.addEventListener('click', ()=>{
  planZoom=1; if(planSvg) planSvg.style.transform='';
  if(planContainer) planContainer.scrollTop=0;
});

function render2D(){
  if(!lastLayout) return;
  hideSkeleton();
  planEmpty?.setAttribute('hidden','');
  const opts={ furniture: toggleFurniture?.checked ?? true, lighting: toggleLighting?.checked ?? true, plumbing: togglePlumbing?.checked ?? true };
  if(typeof renderPlan==='function' && planSvg) renderPlan(planSvg, lastLayout, opts);
  if(planDims) planDims.textContent=`${lastLayout.width.toFixed(1)} × ${lastLayout.height.toFixed(1)} ft · ${lastLayout.built_up_area.toFixed(0)} sqft · ${lastLayout.rooms.length} rooms`;
  if(roomDetails?.hasAttribute('hidden')){
    const first=lastLayout.rooms[0]; if(first) window.onRoomSelect(first);
  }
}
function render3D(){
  if(!lastLayout) return;
  twinEmpty?.setAttribute('hidden','');
  threeCanvas?.removeAttribute('hidden');
  twinOverlay?.removeAttribute('hidden');
  setTimeout(()=>{
    if(window.ThreeViewer){
      window.ThreeViewer.buildFromLayout(lastLayout, { furniture: toggleFurniture3D?.checked ?? true });
      if(twinBadge) twinBadge.textContent=`${lastLayout.rooms.length} rooms · ${lastLayout.furniture.length} furniture · ${lastLayout.lighting.length} lights`;
    }
  }, 120);
}
function renderCompliance(){
  if(!lastCompliance) return;
  complianceStrip?.removeAttribute('hidden');
  const sc=lastCompliance.score; const status=lastCompliance.status;
  if(complianceBadge){
    complianceBadge.textContent=lastCompliance.status_label;
    complianceBadge.className='badge '+(status==='FULLY_COMPLIANT'?'pill-ok':status==='PARTIALLY_COMPLIANT'?'pill-warn':'pill-bad');
    const bg=status==='FULLY_COMPLIANT' ? '#E0F0E8' : status==='PARTIALLY_COMPLIANT' ? '#FFF1D6' : '#FDECEC';
    const bc=status==='FULLY_COMPLIANT' ? '#A7E0C2' : status==='PARTIALLY_COMPLIANT' ? '#E8C07A' : '#E9A6A6';
    const co=status==='FULLY_COMPLIANT' ? '#0F3D26' : status==='PARTIALLY_COMPLIANT' ? '#5A360A' : '#6B0F0F';
    complianceBadge.style.background=bg; complianceBadge.style.borderColor=bc; complianceBadge.style.color=co;
  }
  if(complianceScore){
    complianceScore.textContent=`Score ${sc} · GCN ${lastGCN?lastGCN.score:'—'} (${lastGCN?lastGCN.source:'—'})`;
    if(lastGCN && lastGCN.label_name) complianceScore.textContent=`Score ${sc} · GCN ${lastGCN.score} (${lastGCN.source} · ${lastGCN.label_name})`;
  }
  if(complianceNote){
    const failCount=lastCompliance.failed?lastCompliance.failed.length:0;
    const warnCount=lastCompliance.warnings?lastCompliance.warnings.length:0;
    complianceNote.textContent = failCount===0 ? (warnCount?`${warnCount} soft warnings`:'No hard failures') : `${failCount} hard failures, ${warnCount} warnings`;
  }
  // Inspector validate
  if(inspectorValidate){
    inspectorValidate.innerHTML=`
      <div class="kv"><span>Status</span><span><strong>${lastCompliance.status_label}</strong> · ${lastCompliance.score}</span></div>
      <div class="kv"><span>Rule score</span><span>${lastCompliance.rule_score}</span></div>
      <div class="kv"><span>GCN score</span><span>${lastCompliance.gcn_score ?? (lastGCN?lastGCN.score:'—')} <span style="color:#6B7280">(${lastGCN?lastGCN.source:'—'}${lastGCN&&lastGCN.label_name?' · '+lastGCN.label_name:''})</span>${lastGCN&&lastGCN.note?`<br><span style="font-size:11px; color:#92400E">${lastGCN.note}</span>`:''}</span></div>
      <div class="kv"><span>Checks</span><span>${lastCompliance.passed.length} passed · ${lastCompliance.warnings.length} warnings · ${lastCompliance.failed.length} failed</span></div>
      ${lastCompliance.failed.length ? `<div style="margin-top:8px; padding:8px; background:var(--bad-bg); border:1px solid #E9A6A6; border-radius:8px; font-size:12px; color:#7F1D1D"><strong>Failed</strong><br>${lastCompliance.failed.map(f=>f.label).join('<br>')}</div>`:''}
      ${lastCompliance.warnings.length ? `<div style="margin-top:8px; padding:8px; background:var(--warn-bg); border:1px solid #E8C07A; border-radius:8px; font-size:12px; color:#5A360A"><strong>Warnings</strong><br>${lastCompliance.warnings.map(w=>w.label).join('<br>')}</div>`:''}
      ${lastCompliance.suggestions.length ? `<div style="margin-top:8px"><strong style="font-size:11px; letter-spacing:.06em; text-transform:uppercase">Suggestions</strong><ul style="margin:6px 0; padding-left:18px; font-size:12.5px; color:#334155">${lastCompliance.suggestions.map(s=>`<li>${s}</li>`).join('')}</ul></div>`:''}
    `;
  }
}
function renderReport(){
  if(!lastLayout || !lastCost || !lastCompliance) return;
  const rooms=lastLayout.rooms; const cost=lastCost;
  if(reportGrid){
    reportGrid.innerHTML=`
      <div class="report-card">
        <h3>House specifications</h3>
        <div class="kv"><span>BHK</span><span>${lastParsed.bedrooms}BHK · ${rooms.length} rooms · ${lastParsed.floors} floor(s)</span></div>
        <div class="kv"><span>Built-up area</span><span>${lastLayout.built_up_area.toFixed(0)} sqft (actual room sum ${lastLayout.total_area.toFixed(0)} sqft)</span></div>
        <div class="kv"><span>Footprint</span><span>${lastLayout.width.toFixed(1)} × ${lastLayout.height.toFixed(1)} ft</span></div>
        <div class="kv"><span>Style</span><span>${lastParsed.style}</span></div>
        <div class="kv"><span>Entrance</span><span>${lastParsed.main_entrance_direction} — ${lastLayout.orientation.entrance_wall} wall · Compass ${lastLayout.orientation.compass_label}</span></div>
        <div class="kv"><span>Kitchen type</span><span>${lastParsed.kitchen_type}</span></div>
      </div>
      <div class="report-card">
        <h3>Validation <span class="badge" style="margin-left:auto; background:${lastCompliance.status==='FULLY_COMPLIANT'?'#E0F0E8':'#FFF1D6'}">${lastCompliance.status_label} · ${lastCompliance.score}</span></h3>
        <div class="kv"><span>Rule score</span><span>${lastCompliance.rule_score}</span></div>
        <div class="kv"><span>GCN score</span><span>${lastCompliance.gcn_score ?? (lastGCN?lastGCN.score:'—')} <span style="color:#6B7280">(${lastGCN?lastGCN.source:'—'})</span> ${lastGCN&&lastGCN.note?`<br><span style="font-size:11px; color:#92400E">${lastGCN.note}</span>`:''}</span></div>
        <div class="kv"><span>Passed</span><span>${lastCompliance.passed.length} checks</span></div>
        <div class="kv"><span>Warnings</span><span>${lastCompliance.warnings.length ? lastCompliance.warnings.map(w=>w.label).join('<br>') : 'None'}</span></div>
        ${lastCompliance.failed.length ? `<div class="kv"><span>Failed (hard)</span><span style="color:#7F1D1D">${lastCompliance.failed.map(f=>f.label).join('<br>')}</span></div>`:''}
        <div style="margin-top:10px; font-size:12px; color:#6B7280">Hard failures cap the final score; warnings are soft. GCN · rule weighting is 0.32 · 0.68.</div>
        ${lastCompliance.suggestions.length ? `<div style="margin-top:8px"><strong style="font-size:11px; letter-spacing:.06em; text-transform:uppercase">Suggestions</strong><ul style="margin:6px 0; padding-left:18px; font-size:12.5px; color:#334155">${lastCompliance.suggestions.map(s=>`<li>${s}</li>`).join('')}</ul></div>`:''}
      </div>
      <div class="report-card">
        <h3>Room schedule</h3>
        <div class="cost-item head"><span>Room</span><span>Size</span><span>Area</span><span>Type</span></div>
        ${rooms.map(r=>`<div class="cost-item"><span>${r.label}</span><span>${r.width.toFixed(1)}×${r.height.toFixed(1)} ft</span><span>${r.area.toFixed(0)} sqft</span><span>${r.type}</span></div>`).join('')}
        <div class="kv" style="margin-top:10px"><span>Adjacency</span><span>${lastLayout.adjacency.length} — ${lastLayout.adjacency.map(p=>p.join(' ↔ ')).join(', ') || 'none'}</span></div>
      </div>
      <div class="report-card">
        <h3>Cost estimate — ${cost.profile_label} <span class="badge" style="margin-left:auto">${cost.currency}</span></h3>
        <div class="cost-item head"><span>Item</span><span>Qty</span><span>Rate</span><span>Subtotal</span></div>
        ${cost.items.map(it=>`<div class="cost-item"><span>${it.label}<br><span style="color:#6B7280; font-size:11px">${it.category}</span></span><span>${it.quantity} ${it.unit}</span><span>₹ ${it.rate.toLocaleString()}</span><span>₹ ${it.subtotal.toLocaleString()}</span></div>`).join('')}
        <div class="cost-item total"><span>Grand total · ₹ ${cost.cost_per_sqft.toLocaleString()}/sqft</span><span></span><span></span><span>₹ ${cost.grand_total.toLocaleString()}</span></div>
        <div style="display:grid; grid-template-columns:repeat(${cost.by_category.length},1fr); gap:8px; margin-top:10px">
          ${cost.by_category.map(c=>`<div style="background:var(--stone); border:var(--hair); border-radius:10px; padding:8px; text-align:center"><div style="font-size:10px; color:#6B7280; letter-spacing:.06em; text-transform:uppercase; font-family:JetBrains Mono, monospace">${c.category}</div><div style="font-weight:800">₹ ${c.total.toLocaleString()}</div><div style="font-size:12px; color:#6B7280">${c.pct}%</div></div>`).join('')}
        </div>
        <div style="margin-top:12px">
          <strong style="font-size:11px; letter-spacing:.06em; text-transform:uppercase; font-family:JetBrains Mono, monospace">Assumptions</strong>
          <ul style="margin:6px 0; padding-left:18px; font-size:12px; color:#475569">${cost.assumptions.map(a=>`<li>${a}</li>`).join('')}</ul>
          <strong style="font-size:11px; letter-spacing:.06em; text-transform:uppercase; font-family:JetBrains Mono, monospace">Exclusions</strong>
          <ul style="margin:6px 0; padding-left:18px; font-size:12px; color:#475569">${cost.exclusions.map(a=>`<li>${a}</li>`).join('')}</ul>
          <div style="margin-top:8px; padding:8px; background:#FFF7D6; border:1px solid #E8C07A; border-radius:8px; font-size:12px; color:#5A360A">${cost.note}</div>
        </div>
      </div>
      <div class="report-card">
        <h3>Design assumptions & unresolved</h3>
        <div class="kv"><span>Generation</span><span>Row-band tiling across ${lastLayout.width.toFixed(1)}×${lastLayout.height.toFixed(1)} ft; BHK-proportional areas with min dims.</span></div>
        <div class="kv"><span>Orientation</span><span>${lastLayout.orientation.note}</span></div>
        <div class="kv"><span>GCN mode</span><span>${lastGCN?lastGCN.source:'unknown'}${lastGCN&&lastGCN.label_name?' ('+lastGCN.label_name+')':''} — ${lastGCN&&lastGCN.source.includes('baseline')?'Deterministic heuristic; place gcn_model.pth + gcn_config.json for learned (7→128, Partial/Compliant)':'Claude GCN 7→128 Partial/Compliant 90.46% test'}</span></div>
        <div class="kv"><span>Limitations</span><span>Single-floor; plumbing is Manhattan planning routes; lighting is visualization not lux; rates require local verification.</span></div>
        ${lastLayout.metadata.warnings && lastLayout.metadata.warnings.length ? `<div class="kv"><span>Warnings</span><span>${lastLayout.metadata.warnings.join('<br>')}</span></div>`:''}
        <div style="margin-top:10px; display:flex; gap:8px; flex-wrap:wrap">
          <button class="btn btn-sm btn-ghost" onclick="window.downloadReport()">Download JSON report</button>
          <button class="btn btn-sm btn-ghost" onclick="window.print()">Print report</button>
        </div>
      </div>
    `;
  }
  // Inspector cost
  if(inspectorCost){
    const cost=lastCost;
    inspectorCost.innerHTML=`
      <div class="kv"><span>Profile</span><span>${cost.profile_label}</span></div>
      <div class="kv"><span>Total</span><span><strong>₹ ${cost.grand_total.toLocaleString()}</strong> · ${cost.cost_per_sqft.toLocaleString()}/sqft</span></div>
      <div style="margin-top:10px">
        ${cost.by_category.map(c=>`<div class="kv"><span>${c.category}</span><span>₹ ${c.total.toLocaleString()} · ${c.pct}%</span></div>`).join('')}
      </div>
      <div style="margin-top:10px; padding:8px; background:var(--stone); border:var(--hair); border-radius:8px; font-size:11.5px; color:#5A360A">${cost.note}</div>
      <button class="btn btn-ghost btn-sm" style="margin-top:10px; width:100%" onclick="window.downloadReport()">View full breakdown in Report →</button>
    `;
  }
  // Inspector systems
  if(inspectorSystems){
    inspectorSystems.innerHTML=`
      <div class="kv"><span>Furniture</span><span>${lastLayout.furniture.length} items — ${Array.from(new Set(lastLayout.furniture.map(f=>f.type))).join(', ')}</span></div>
      <div class="kv"><span>Lighting</span><span>${lastLayout.lighting.length} fixtures — ${Array.from(new Set(lastLayout.lighting.map(l=>l.type))).join(', ')}</span></div>
      <div class="kv"><span>Fixtures</span><span>${lastLayout.plumbing_fixtures.length} — ${lastLayout.plumbing_fixtures.map(p=>p.label).join(', ')}</span></div>
      <div class="kv"><span>Routes</span><span>${lastLayout.plumbing_routes.length} routes — supply solid, drainage dashed</span></div>
      <div class="kv"><span>Orientation</span><span>${lastLayout.orientation.entrance_wall} wall · ${lastLayout.orientation.compass_label} · ${lastLayout.orientation.north_angle_deg}°</span></div>
      <div class="kv"><span>Adjacency</span><span>${lastLayout.adjacency.map(p=>p.join(' ↔ ')).join('<br>') || 'none'}</span></div>
      <p style="margin-top:10px; font-size:11px; color:#6B7280; line-height:1.5">Furniture wall-aligned with door clearance. Lighting via Three.js point/ambient (not photometric). Plumbing routes are Manhattan planning lines.</p>
    `;
  }
}
function renderAll(data){
  render2D(); render3D(); renderCompliance(); renderReport(); hideSkeleton();
}

// Model status — honest display
async function refreshModelStatus(){
  try{
    const r=await fetch(API.modelStatus);
    const j=await r.json();
    const mode=j.inference_mode || 'baseline';
    const isTrained = mode.includes('gcn_trained');
    const isClaude = mode==='gcn_trained_claude';
    const hasTorch=j.has_torch, modelExists=j.model_exists;
    let pillText, pillClass, statusText;
    if(isTrained){
      pillText = isClaude ? 'Trained · gcn_trained_claude' : 'Trained · gcn_trained';
      pillClass = 'trained';
      statusText = isClaude ? 'Trained · Claude GCN (7→128)' : 'Trained · GCN';
    } else {
      pillText = modelExists && !hasTorch ? 'Model found · needs torch' : 'Baseline · deterministic';
      pillClass = 'baseline';
      statusText = hasTorch===false ? 'Baseline (torch unavailable)' : 'Baseline · heuristic';
    }
    if(modelPill){
      modelPill.textContent=pillText;
      modelPill.className='model-pill '+pillClass;
      modelPill.removeAttribute('hidden');
      modelPill.title=`${mode} · torch:${hasTorch} · exists:${modelExists} · ${j.is_claude_model?'7 feats':'14 feats'}`;
    }
    if(studioStatusPill){
      studioStatusPill.textContent=statusText;
      studioStatusPill.className='status-pill '+(isTrained?'ok':'warn');
      studioStatusPill.title=JSON.stringify({mode, is_claude_model:j.is_claude_model, has_torch:hasTorch},null,2);
    }
    console.log('model status', j);
  }catch(e){ console.warn('model status failed', e); if(studioStatusPill) studioStatusPill.textContent='Status unavailable'; }
}
fetch(API.health).then(r=>r.json()).then(j=>console.log('health',j)).catch(()=>{});
refreshModelStatus();
setInterval(refreshModelStatus, 30000);

// Expose
window.doGenerate=doGenerate;
window.renderAll=renderAll;
