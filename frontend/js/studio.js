// IntelliTwin Studio — vanilla JS controller. Preserves the original backend contract and override logic.
(function () {
  const API = window.IntelliAPI;
  const $ = id => document.getElementById(id);
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const inr = n => '₹ ' + Math.round(n || 0).toLocaleString('en-IN');
  const kv = (k, v) => `<div class="kv"><span>${esc(k)}</span><span>${v}</span></div>`;

  const PRESETS = {
    bhk3: "I want a modern 3BHK house with 1500 square feet of built-up area, three bedrooms, two bathrooms, an open kitchen, a living room, and an east-facing main entrance.",
    bhk2: "2BHK minimal house, 1100 sqft, 2 bedrooms, 2 bathrooms, open kitchen, living and dining combined, one balcony, north facing entrance.",
    bhk4: "Luxury 4BHK villa 2200 sqft, 4 bedrooms, 3 bathrooms, open kitchen, dining, living, 2 balconies, south facing, modern style.",
    studio: "1BHK compact 650 sqft, 1 bedroom, 1 bathroom, open kitchen, living hall, east facing."
  };

  const S = { result: null, lastParsed: null, busy: false, view: 'plan', zoom: 1, selected: null, activeFloor: 0,
    l2: { furniture: true, lighting: true, plumbing: true, dimensions: true }, l3: { walls: true, furniture: true, lighting: true, plumbing: true } };

  const req = $('reqInput'), cfg = {
    bedrooms: $('cfgBedrooms'), bathrooms: $('cfgBathrooms'), balconies: $('cfgBalconies'), area: $('cfgArea'),
    style: $('cfgStyle'), kitchen: $('cfgKitchen'), direction: $('cfgDirection'), floors: $('cfgFloors')
  };

  // ---------- toast ----------
  let tt; function toast(m) { const t = $('toast'); t.textContent = m; t.hidden = false; clearTimeout(tt); tt = setTimeout(() => t.hidden = true, 3200); }

  // ---------- model status (honest) ----------
  async function refreshStatus() {
    const pill = $('modelPill');
    pill.className = 'pill loading'; pill.textContent = 'Checking model…';
    try {
      const j = await API.modelStatus();
      const mode = j.inference_mode || 'baseline';
      const trained = mode.includes('gcn_trained'), claude = mode === 'gcn_trained_claude';
      if (trained) { pill.className = 'pill ok'; pill.textContent = claude ? 'Trained · Claude GCN (7→128)' : 'Trained · GCN'; }
      else { pill.className = 'pill warn'; pill.textContent = j.model_exists && !j.has_torch ? 'Model found · needs torch' : 'Baseline · deterministic'; }
      pill.title = `${mode} · torch: ${j.has_torch} · model file: ${j.model_exists}`;
    } catch (e) {
      pill.className = 'pill bad'; pill.textContent = 'Backend unreachable'; pill.title = e.message;
    }
    try {
      const r = await API.rates(); const src = r && (r.profiles || r);
      let list = Array.isArray(src) ? src.map(p => [p.id || p.key || p.name, p.label || p.name || p.id])
        : (src && typeof src === 'object') ? Object.entries(src).map(([k, v]) => [k, (v && v.label) || k]) : [];
      list = list.filter(x => x[0]);
      if (list.length) {
        const sel = $('rateProfile'), cur = sel.value;
        sel.innerHTML = list.map(([id, l]) => `<option value="${esc(id)}">${esc(l)}</option>`).join('');
        if (list.some(x => x[0] === cur)) sel.value = cur;
      }
    } catch { /* keep default profile */ }
  }
  $('modelPill').addEventListener('click', refreshStatus);

  // ---------- config sync ----------
  function readCfg() {
    return { bedrooms: +cfg.bedrooms.value, bathrooms: +cfg.bathrooms.value, balconies: +cfg.balconies.value, area: +cfg.area.value,
      style: cfg.style.value, kitchen: cfg.kitchen.value, direction: cfg.direction.value, floors: +cfg.floors.value };
  }
  function setSelect(el, v) { if (![...el.options].some(o => o.value === v)) el.add(new Option(String(v).replace(/_/g, ' '), v)); el.value = v; }
  function syncFromParsed(p) {
    if (!p) return;
    cfg.bedrooms.value = p.bedrooms; cfg.bathrooms.value = p.bathrooms; cfg.balconies.value = p.balconies ?? 0;
    cfg.area.value = Math.round(p.total_area_sqft); setSelect(cfg.style, p.style || 'modern'); setSelect(cfg.kitchen, p.kitchen_type || 'open');
    setSelect(cfg.direction, p.main_entrance_direction || 'east'); setSelect(cfg.floors, String(p.floors || 1));
  }
  function buildOverride(text) {
    const c = readCfg(), last = S.lastParsed;
    const base = { original_text: text, bedrooms: c.bedrooms, bathrooms: c.bathrooms, balconies: c.balconies, kitchens: 1, living_rooms: 1,
      total_area_sqft: c.area, kitchen_type: c.kitchen, style: c.style, floors: c.floors, main_entrance_direction: c.direction,
      wants_furniture: true, wants_lighting: true, wants_plumbing: true,
      explicit: { bedrooms: true, bathrooms: true, area: true, direction: true, balcony: true, kitchen_type: true },
      warnings: [], inferred_defaults: { area: false, direction: false } };
    if (!last) return Object.assign(base, { dining_rooms: c.bedrooms >= 3 ? 1 : 0 });
    const differs = c.bedrooms !== last.bedrooms || c.bathrooms !== last.bathrooms || c.balconies !== (last.balconies || 0) ||
      Math.abs(c.area - last.total_area_sqft) > 1 || c.style !== last.style || c.kitchen !== last.kitchen_type ||
      c.direction !== last.main_entrance_direction || c.floors !== (last.floors || 1);
    return differs ? Object.assign(base, { dining_rooms: last.dining_rooms || 0 }) : null;
  }

  // ---------- parse preview ----------
  let pt;
  req.addEventListener('input', () => {
    clearTimeout(pt);
    pt = setTimeout(async () => {
      const text = req.value.trim(), box = $('parsePreview');
      if (text.length < 10) { box.hidden = true; return; }
      try {
        const p = await API.parse(text); if (!p) return;
        S.lastParsed = p; syncFromParsed(p);
        box.hidden = false;
        box.innerHTML = `<p class="eyebrow">Parsed preview</p><div class="grid">
          <span>Bed ${esc(p.bedrooms)} ${p.explicit && p.explicit.bedrooms ? '· explicit' : '· inferred'}</span><span>Bath ${esc(p.bathrooms)}</span>
          <span>${Math.round(p.total_area_sqft)} sqft ${p.inferred_defaults && p.inferred_defaults.area ? '· inferred' : ''}</span><span>${esc(p.main_entrance_direction)}</span>
          <span>${esc(p.kitchen_type)} kitchen</span><span>${esc(p.style)}</span></div>
          ${p.warnings && p.warnings.length ? `<ul>${p.warnings.map(w => `<li>• ${esc(w)}</li>`).join('')}</ul>` : ''}`;
      } catch { /* preview optional */ }
    }, 500);
  });
  document.querySelectorAll('[data-preset]').forEach(b => b.addEventListener('click', () => { req.value = PRESETS[b.dataset.preset]; req.dispatchEvent(new Event('input')); req.focus(); }));
  $('sampleBtn').addEventListener('click', () => { req.value = PRESETS.bhk3; req.dispatchEvent(new Event('input')); });

  // ---------- generate ----------
  function setBusy(b) {
    S.busy = b;
    const g = $('generateBtn'); g.disabled = b; $('resetBtn').disabled = b; req.disabled = b;
    g.querySelector('.spinner').hidden = !b; g.querySelector('.gen-ico').style.display = b ? 'none' : '';
    g.querySelector('.btn-label').textContent = b ? 'Generating design…' : 'Generate Design';
    $('planSkeleton').hidden = !b; if (b) $('planEmpty').hidden = true;
    const pill = $('modelPill');
    if (b) { pill.dataset.prev = pill.className + '|' + pill.textContent; pill.className = 'pill busy'; pill.textContent = 'Generation in progress'; }
    else if (pill.dataset.prev) { const [c, t] = pill.dataset.prev.split('|'); pill.className = c; pill.textContent = t; }
    $('footGen').textContent = b ? 'Generating — tiling, furniture, GCN scoring…' : $('footGen').textContent;
  }
  async function doGenerate() {
    const text = req.value.trim(), err = $('errorBox');
    if (!text) { err.textContent = 'Please describe your house requirements.'; err.hidden = false; req.focus(); return; }
    if (S.busy) return;
    err.hidden = true; setBusy(true);
    try {
      const payload = { text, rate_profile: $('rateProfile').value || 'india_tier2_2025', max_retries: 3 };
      const o = buildOverride(text); if (o) payload.parsed = o;
      const d = await API.generate(payload);
      S.result = d; S.lastParsed = d.parsed; syncFromParsed(d.parsed); S.selected = d.layout.rooms[0] || null; S.zoom = 1;
      S.activeFloor = 0; syncFloorSelect();
      setBusy(false); renderAll(); setView('plan');
      toast(`Generated — ${d.compliance.status_label} (${d.compliance.score})`);
    } catch (e) {
      setBusy(false);
      err.textContent = e.message === 'Failed to fetch' ? 'Could not reach the IntelliTwin backend. Check the server address in Settings.' : (e.message || 'Generation failed.');
      err.hidden = false; $('footGen').textContent = 'Generation failed';
      if (!S.result) $('planEmpty').hidden = false;
    }
  }
  $('generateBtn').addEventListener('click', doGenerate);
  document.addEventListener('keydown', e => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') { e.preventDefault(); doGenerate(); }
    if (e.key === 'Escape') { $('exportMenu').hidden = true; $('settingsModal').hidden = true; }
  });

  $('resetBtn').addEventListener('click', () => {
    window.ThreeViewer?.disposeThree(); $('room3DBadge').hidden = true;
    req.value = ''; S.result = null; S.lastParsed = null; S.selected = null; S.activeFloor = 0; S.zoom = 1;
    $('parsePreview').hidden = true; $('errorBox').hidden = true; $('planSvg').hidden = true; $('planSvg').innerHTML = '';
    $('planEmpty').hidden = false; $('planDims').hidden = true; $('twinEmpty').hidden = false; $('twinBadge').hidden = true;
    $('floorSelect').hidden = true; $('floorSelect').innerHTML = '';
    $('inspector').hidden = true; $('exportBtn').disabled = true; $('camReset').disabled = $('camTop').disabled = true;
    $('projectName').textContent = 'Untitled residence'; $('projectSub').textContent = 'No generation yet';
    $('footGen').textContent = 'Idle — ready'; $('footWarn').textContent = ''; renderReport(); toast('Reset complete');
  });

  // ---------- views ----------
  function setView(v) {
    S.view = v;
    document.querySelectorAll('[data-view]').forEach(b => b.classList.toggle('active', b.dataset.view === v));
    $('panel-plan').classList.toggle('off', v !== 'plan');
    $('panel-twin').classList.toggle('off', v !== 'twin');
    $('panel-report').hidden = v !== 'report';
    if (v === 'twin') setTimeout(() => window.dispatchEvent(new Event('resize')), 60);
  }
  document.querySelectorAll('[data-view]').forEach(b => b.addEventListener('click', () => setView(b.dataset.view)));
  $('sideToggle').addEventListener('click', () => $('side').classList.toggle('closed'));
  if (window.innerWidth < 1024) $('side').classList.add('closed');

  // Active floor plan for the 2D view. Single-floor designs return the layout itself.
  function currentPlan() {
    if (!S.result) return null;
    const L = S.result.layout;
    return (L.floor_plans || [])[S.activeFloor] || L;
  }
  // Keep the floor selector in sync with the generated design.
  function syncFloorSelect() {
    const fs = $('floorSelect'), L = S.result && S.result.layout;
    const floors = L && L.floors > 1 ? L.floors : 1;
    fs.hidden = floors <= 1;
    if (!fs.hidden) {
      fs.innerHTML = (L.floor_plans || []).map(fp => `<option value="${fp.floor_index}">${esc(fp.label)}</option>`).join('');
      fs.value = S.activeFloor;
    }
  }
  // ---------- 2D ----------
  window.onRoomSelect = room => { S.selected = room; window.ThreeViewer?.selectRoom(room.id); window.PlanView.select($('planSvg'), room.id); renderInspector(); };
  const PV = window.PlanView;
  const setZoomLbl = z => { $('zoomLbl').textContent = Math.round(z * 100) + '%'; };
  PV.onChange($('planSvg'), setZoomLbl);
  function render2D() {
    if (!S.result) return;
    const svg = $('planSvg'); svg.hidden = false; $('planEmpty').hidden = true;
    const L = S.result.layout, plan = currentPlan();
    const view = {
      ...L,
      width: plan.width, height: plan.height,
      rooms: plan.rooms,
      furniture: plan.furniture,
      lighting: plan.lighting,
      doors: plan.doors,
      windows: plan.windows,
      plumbing_fixtures: plan.plumbing_fixtures,
      plumbing_routes: plan.plumbing_routes,
      total_area: plan.total_area,
    };
    renderPlan(svg, view, S.l2);
    if (S.selected) PV.select(svg, S.selected.id);
    const d = $('planDims'); d.hidden = false;
    const issues = PV.issues(svg);
    d.textContent = `${(plan.label || 'Ground Floor')} · ${view.width.toFixed(1)} × ${view.height.toFixed(1)} ft · ${(plan.total_area || view.total_area).toFixed(0)} sqft · ${view.rooms.length} rooms · drag to pan · scroll to zoom · click a room to inspect`
      + (issues.length ? ` · ⚠ backend geometry: ${issues.map(i => `${i.a} overlaps ${i.b} (${(i.w * i.h).toFixed(0)} sqft)`).join('; ')}` : '');
  }
  $('floorSelect').addEventListener('change', () => {
    if (!S.result) return;
    S.activeFloor = +$('floorSelect').value;
    render2D(); renderInspector();
    window.ThreeViewer?.setFloorHighlight(S.activeFloor);
  });
  document.querySelectorAll('[data-layer2d]').forEach(b => b.addEventListener('click', () => {
    const k = b.dataset.layer2d; S.l2[k] = !S.l2[k]; b.setAttribute('aria-pressed', S.l2[k]); render2D();
  }));
  $('zoomIn').addEventListener('click', () => S.result && PV.zoomBy($('planSvg'), 1.25));
  $('zoomOut').addEventListener('click', () => S.result && PV.zoomBy($('planSvg'), 0.8));
  $('zoomFit').addEventListener('click', () => S.result && PV.fit($('planSvg')));

  // ---------- 3D ----------
  const TV = () => window.ThreeViewer;
  function apply3DLayers() {
    const t = TV(); if (!t) return;
    t.setWallsVisible(S.l3.walls); t.setFurnitureVisible(S.l3.furniture); t.setLightingVisible(S.l3.lighting); t.setPlumbingVisible(S.l3.plumbing);
  }
  function render3D() {
    const L = S.result.layout;
    $('twinEmpty').hidden = true; $('camReset').disabled = $('camTop').disabled = false;
    const b = $('twinBadge'); b.hidden = false;
    const totalRooms = (L.floor_plans || []).reduce((sum, fp) => sum + fp.rooms.length, 0) || L.rooms.length;
    b.textContent = `${totalRooms} rooms across ${L.floors || 1} floor(s) · ${(L.furniture || []).length} furniture · ${(L.lighting || []).length} lights · drag to orbit · right-drag to pan · scroll to zoom`;
    const go = () => { const t = TV(); if (!t) return setTimeout(go, 150); t.buildFromLayout(L, { style: S.result.parsed.style }); t.selectRoom(S.selected?.id); t.setFloorHighlight(S.activeFloor); apply3DLayers(); window.dispatchEvent(new Event('resize')); };
    setTimeout(go, 120);
  }
  document.querySelectorAll('[data-layer3d]').forEach(b => b.addEventListener('click', () => {
    const k = b.dataset.layer3d; S.l3[k] = !S.l3[k]; b.setAttribute('aria-pressed', S.l3[k]); apply3DLayers();
  }));
  $('camReset').addEventListener('click', () => TV() && TV().resetCamera());
  $('camTop').addEventListener('click', () => TV() && TV().topView());
  $('cutawayBtn').addEventListener('click', e => {
    const b = e.currentTarget, active = b.getAttribute('aria-pressed') !== 'true';
    b.setAttribute('aria-pressed', active); TV()?.setCutaway(active);
  });
  document.querySelectorAll('[data-lighting-mode]').forEach(b => b.addEventListener('click', () => {
    TV()?.setLightingMode(b.dataset.lightingMode);
    document.querySelectorAll('[data-lighting-mode]').forEach(x => x.setAttribute('aria-pressed', x === b));
  }));

  // ---------- inspector ----------
  function renderInspector() {
    const r = S.result, el = $('inspector'); if (!r) { el.hidden = true; return; }
    el.hidden = false;
    const { layout: L, compliance: C, cost: K, gcn: G } = r;
    const plan = currentPlan() || L;
    const tone = C.status === 'FULLY_COMPLIANT' ? 'ok' : C.status === 'PARTIALLY_COMPLIANT' ? 'warn' : 'bad';
    const sel = S.selected;
    el.innerHTML = `
      <div><p class="eyebrow">Validation</p>
        <div class="score ${tone}"><span>${esc(C.status_label)}</span><b>${esc(C.score)}</b></div>
        <div style="margin-top:10px">${kv('Rule score', esc(C.rule_score))}
        ${kv('GCN score', `${esc(C.gcn_score ?? (G ? G.score : '—'))} (${esc(G ? G.source : '—')}${G && G.label_name ? ' · ' + esc(G.label_name) : ''})`)}
        ${kv('Checks', `${C.passed.length} pass · ${C.warnings.length} warn · ${C.failed.length} fail`)}</div>
        ${G && G.note ? `<p class="small" style="color:var(--warn-ink)">${esc(G.note)}</p>` : ''}
        <p class="small">Heuristic design check — not a certified building-code approval.</p></div>
      ${sel ? `<div><p class="eyebrow">Selected room</p><p class="room-title">${esc(sel.label)}</p><div style="margin-top:6px">
        ${kv('Type', esc(sel.type))}${kv('Size', `${sel.width.toFixed(1)} × ${sel.height.toFixed(1)} ft`)}${kv('Area', `${sel.area.toFixed(0)} sqft`)}</div></div>` : ''}
      <div><p class="eyebrow">Cost estimate</p><p class="big">${inr(K.grand_total)}</p>
        <p class="mono muted" style="font-size:11px">${inr(K.cost_per_sqft)}/sqft · ${esc(K.profile_label)}</p>
        <div style="margin-top:12px;display:flex;flex-direction:column;gap:8px">${K.by_category.map(c => `<div><div class="kv"><span style="text-transform:capitalize">${esc(c.category)}</span><span class="mono">${esc(c.pct)}%</span></div><div class="bar"><i style="width:${+c.pct || 0}%"></i></div></div>`).join('')}</div>
        <p class="small">Estimate only — not a contractor quotation.</p></div>
      <div><p class="eyebrow">Systems</p><div style="margin-top:8px">
        ${kv('Furniture', `${plan.furniture.length} items`)}${kv('Lighting', `${plan.lighting.length} fixtures`)}
        ${kv('Plumbing', `${plan.plumbing_fixtures.length} fixtures · ${plan.plumbing_routes.length} routes`)}
        ${kv('Orientation', `${esc(L.orientation.entrance_wall)} wall · ${esc(L.orientation.compass_label)}`)}</div></div>`;
  }

  // ---------- report ----------
  function renderReport() {
    const el = $('reportGrid'), r = S.result;
    if (!r) { el.innerHTML = `<div class="empty" style="position:static;min-height:60vh"><div><h3>Report empty</h3><p>Generate a design to see validation, the room schedule and the cost sheet.</p></div></div>`; return; }
    const { layout: L, compliance: C, cost: K, gcn: G, parsed: P } = r;
    el.innerHTML = `
      <div><p class="eyebrow">Design report</p><h2>${esc(P.bedrooms)}BHK · ${Math.round(P.total_area_sqft)} sqft · ${esc(P.style)}</h2></div>
      <div class="rgrid">
        <div class="rcard"><h3>House specifications</h3>
          ${kv('Configuration', `${esc(P.bedrooms)}BHK · ${L.rooms.length} rooms · ${esc(P.floors)} floor(s)`)}
          ${kv('Built-up area', `${L.built_up_area.toFixed(0)} sqft (room sum ${L.total_area.toFixed(0)})`)}
          ${kv('Footprint', `${L.width.toFixed(1)} × ${L.height.toFixed(1)} ft`)}
          ${kv('Entrance', `${esc(P.main_entrance_direction)} — ${esc(L.orientation.entrance_wall)} wall · ${esc(L.orientation.compass_label)}`)}
          ${kv('Kitchen', esc(P.kitchen_type))}</div>
        <div class="rcard"><h3>Validation</h3>
          ${kv('Status', `${esc(C.status_label)} · ${esc(C.score)}`)}${kv('Rule score', esc(C.rule_score))}
          ${kv('GCN score', `${esc(C.gcn_score ?? (G ? G.score : '—'))} (${esc(G ? G.source : '—')})`)}
          <ul class="checks">${C.failed.map(f => `<li class="f">✕ ${esc(f.label)}</li>`).join('')}${C.warnings.map(w => `<li class="w">! ${esc(w.label)}</li>`).join('')}${C.passed.map(p => `<li class="p">✓ ${esc(p.label ?? p)}</li>`).join('')}</ul>
          ${C.suggestions.length ? `<p class="eyebrow" style="margin-top:14px">Suggestions</p><ul class="list">${C.suggestions.map(s => `<li>${esc(s)}</li>`).join('')}</ul>` : ''}
          <p class="small">Hard failures cap the final score; warnings are soft. GCN · rule weighting is 0.32 · 0.68.</p></div>
      </div>
      <div class="rcard"><h3>Room schedule</h3><table><thead><tr><th>Room</th><th>Size</th><th>Area</th><th>Type</th></tr></thead><tbody>
        ${L.floor_plans ? L.floor_plans.map(fp => `<h4>${esc(fp.label)}</h4><table><thead><tr><th>Room</th><th>Size</th><th>Area</th><th>Type</th></tr></thead><tbody>${fp.rooms.map(rm => `<tr><td>${esc(rm.label)}</td><td class="mono">${rm.width.toFixed(1)}×${rm.height.toFixed(1)} ft</td><td class="mono">${rm.area.toFixed(0)} sqft</td><td>${esc(rm.type)}</td></tr>`).join('')}</tbody></table>`).join('') : L.rooms.map(rm => `<tr><td>${esc(rm.label)}</td><td class="mono">${rm.width.toFixed(1)}×${rm.height.toFixed(1)} ft</td><td class="mono">${rm.area.toFixed(0)} sqft</td><td>${esc(rm.type)}</td></tr>`).join('')}
        </tbody></table><p class="small">Adjacency: ${L.adjacency.map(p => p.map(esc).join(' ↔ ')).join(', ') || 'none'}</p></div>
      <div class="rcard"><h3>Cost estimate — ${esc(K.profile_label)} <span class="mono muted" style="font-size:12px">${esc(K.currency)}</span></h3>
        <table><thead><tr><th>Item</th><th>Qty</th><th class="num">Rate</th><th class="num">Subtotal</th></tr></thead><tbody>
        ${K.items.map(it => `<tr><td>${esc(it.label)}<br><span class="muted" style="font-size:10px">${esc(it.category)}</span></td><td class="mono">${esc(it.quantity)} ${esc(it.unit)}</td><td class="num">${inr(it.rate)}</td><td class="num">${inr(it.subtotal)}</td></tr>`).join('')}
        </tbody><tfoot><tr><td>Grand total · ${inr(K.cost_per_sqft)}/sqft</td><td></td><td></td><td class="num">${inr(K.grand_total)}</td></tr></tfoot></table>
        <div class="rgrid" style="margin-top:16px"><div><p class="eyebrow">Assumptions</p><ul class="list">${K.assumptions.map(a => `<li>${esc(a)}</li>`).join('')}</ul></div>
        <div><p class="eyebrow">Exclusions</p><ul class="list">${K.exclusions.map(a => `<li>${esc(a)}</li>`).join('')}</ul></div></div>
        ${K.note ? `<p class="note">${esc(K.note)}</p>` : ''}</div>
      <div class="rcard"><h3>Model &amp; limitations</h3>${kv('GCN source', `${esc(G ? G.source : '—')}${G && G.label_name ? ' · ' + esc(G.label_name) : ''}`)}
        <p class="small">Plumbing uses Manhattan planning routes; lighting is visualization, not lux; rates require local verification.</p></div>`;
  }

  function renderAll() {
    const { layout: L, parsed: P, compliance: C, gcn: G } = S.result;
    render2D(); render3D(); renderInspector(); renderReport();
    $('exportBtn').disabled = false;
    $('projectName').textContent = `${P.bedrooms}BHK · ${Math.round(P.total_area_sqft)} sqft · ${P.style}`;
    const totalRooms = (L.floor_plans || []).reduce((sum, fp) => sum + fp.rooms.length, 0) || L.rooms.length;
    $('projectSub').textContent = `${L.width.toFixed(1)}×${L.height.toFixed(1)} ft · ${totalRooms} rooms · ${P.floors} floor(s) · ${P.main_entrance_direction} facing`;
    $('footGen').textContent = `Generated ${totalRooms} rooms across ${P.floors} floor(s) · ${C.status_label} ${C.score} · GCN ${G ? G.source : '—'}`;
    $('footWarn').textContent = C.failed.length ? `${C.failed.length} hard failures` : C.warnings.length ? `${C.warnings.length} warnings` : 'No hard failures';
  }

  // ---------- export ----------
  function download(name, blob) { const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = name; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 1000); }
  function exportPng() {
    const svg = $('planSvg'), vb = svg.viewBox.baseVal, w = vb && vb.width || 1000, h = vb && vb.height || 800, sc = 2000 / w;
    const img = new Image();
    img.onload = () => { const c = document.createElement('canvas'); c.width = w * sc; c.height = h * sc; const x = c.getContext('2d');
      x.fillStyle = '#FBFAF7'; x.fillRect(0, 0, c.width, c.height); x.drawImage(img, 0, 0, c.width, c.height);
      c.toBlob(b => { download('intellitwin-floorplan.png', b); toast('Floorplan PNG downloaded'); }); };
    img.onerror = () => toast('Could not render the PNG');
    img.src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(new XMLSerializer().serializeToString(svg));
  }
  $('exportBtn').addEventListener('click', e => { e.stopPropagation(); $('exportMenu').hidden = !$('exportMenu').hidden; });
  document.addEventListener('click', () => $('exportMenu').hidden = true);
  document.querySelectorAll('[data-export]').forEach(b => b.addEventListener('click', () => {
    if (!S.result) return;
    const k = b.dataset.export;
    if (k === 'json') { download('intellitwin-design.json', new Blob([JSON.stringify(S.result, null, 2)], { type: 'application/json' })); toast('Design JSON downloaded'); }
    if (k === 'png') exportPng();
    if (k === 'print') { setView('report'); setTimeout(() => window.print(), 150); }
  }));

  // ---------- settings ----------
  $('settingsBtn').addEventListener('click', () => { $('apiBaseInput').value = API.getBase(); $('settingsModal').hidden = false; });
  $('settingsCancel').addEventListener('click', () => $('settingsModal').hidden = true);
  $('settingsModal').addEventListener('click', e => { if (e.target.id === 'settingsModal') e.target.hidden = true; });
  $('settingsSave').addEventListener('click', () => { API.setBase($('apiBaseInput').value); $('settingsModal').hidden = true; refreshStatus(); toast('Backend address saved'); });

  renderReport();
  refreshStatus();
})();
