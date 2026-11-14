// IntelliTwin 2D Viewer — SVG floorplan renderer.
//
// Coordinate model (the fix for the old overlap bug):
//   * Geometry (rooms, walls, furniture, plumbing routes) is drawn in WORLD units (feet)
//     inside one <g> with a single world->screen transform  X = tx + x*s,  Y = ty + y*s.
//     Strokes use vector-effect="non-scaling-stroke" so line weights stay constant.
//   * All text, markers, dimension lines, scale bar, compass and legend are drawn in
//     SCREEN pixels. Their size never depends on the plan size or zoom.
//   * The old renderer set fixed font sizes in feet (6 ft names, 4.5 ft dimensions,
//     3.2 ft furniture labels) — on a ~10 ft room those were half the room tall, so every
//     label spilled into its neighbours. Labels now fit-test against the room's on-screen box.
//   * Zoom/pan modify (s, tx, ty) and re-render; no CSS transform scaling of the SVG.
// Data comes unchanged from the backend layout JSON.
(function () {
  const NS = "http://www.w3.org/2000/svg";

  const ROOM = {
    living_room: { fill: "#EEF0EC", text: "#2E3A33" },
    bedroom: { fill: "#E8EEE6", text: "#2B3F2F" },
    kitchen: { fill: "#F6EFDC", text: "#5A4413" },
    bathroom: { fill: "#E7ECF2", text: "#2D3D52" },
    balcony: { fill: "#F5EEE9", text: "#5E3B2A" },
    dining_room: { fill: "#F4EBE1", text: "#5B3A1D" },
    corridor: { fill: "#F1EFEA", text: "#4A443C" },
    entrance: { fill: "#F3F0EA", text: "#4A443C" },
    staircase: { fill: "#E9E7DE", text: "#4A443C" }
  };
  const SHORT = { living_room: "Living", bedroom: "Bed", kitchen: "Kitchen", bathroom: "Bath", balcony: "Balc.", dining_room: "Dining", corridor: "Corr.", entrance: "Entry", staircase: "Stair" };
  const C = {
    paper: "#FCFAF6", grid: "#EEE9E0", gridMajor: "#E2DBCF", extWall: "#2A2622", intWall: "#7D746A",
    furnFill: "rgba(42,38,34,0.06)", furnStroke: "#8C8378", dim: "#5E574E", water: "#0E8FC4", drain: "#7A4FC9",
    light: "#D9A21B", select: "#B5653C", warn: "#C2410C", window: "#5FB4DA"
  };
  const SANS = "Manrope, system-ui, sans-serif", MONO = "'JetBrains Mono', ui-monospace, monospace";

  const states = new WeakMap();

  function el(tag, attrs, parent) {
    const e = document.createElementNS(NS, tag);
    if (attrs) for (const k in attrs) e.setAttribute(k, String(attrs[k]));
    if (parent) parent.appendChild(e);
    return e;
  }
  const num = (v, d = 0) => (typeof v === "number" && isFinite(v) ? v : d);
  const fmt = v => (Math.round(num(v) * 10) / 10).toFixed(1);
  const title = (parent, t) => { el("title", null, parent).textContent = t; };
  const prettyType = t => String(t || "item").replace(/_/g, " ");

  function textWidth(t, fallbackFs, mono) {
    let w = 0;
    try { w = t.getComputedTextLength(); } catch (e) { w = 0; }
    if (!w) w = (t.textContent || "").length * fallbackFs * (mono ? 0.62 : 0.6);
    return w;
  }
  const hit = (a, b) => a.x < b.x + b.w && a.x + a.w > b.x && a.y < b.y + b.h && a.y + a.h > b.y;

  // ---------- geometry analysis ----------
  function bounds(L) {
    let x0 = 0, y0 = 0, x1 = num(L.width, 40), y1 = num(L.height, 40);
    (L.rooms || []).forEach(r => {
      x0 = Math.min(x0, r.x); y0 = Math.min(y0, r.y);
      x1 = Math.max(x1, r.x + r.width); y1 = Math.max(y1, r.y + r.height);
    });
    return { x0, y0, x1, y1, w: x1 - x0, h: y1 - y0 };
  }

  // Overlapping rooms are reported, never silently moved.
  function findOverlaps(rooms) {
    const out = [];
    for (let i = 0; i < rooms.length; i++) for (let j = i + 1; j < rooms.length; j++) {
      const a = rooms[i], b = rooms[j];
      const x0 = Math.max(a.x, b.x), y0 = Math.max(a.y, b.y);
      const x1 = Math.min(a.x + a.width, b.x + b.width), y1 = Math.min(a.y + a.height, b.y + b.height);
      if (x1 - x0 > 0.05 && y1 - y0 > 0.05 && (x1 - x0) * (y1 - y0) > 0.25)
        out.push({ a: a.label || a.id, b: b.label || b.id, x: x0, y: y0, w: x1 - x0, h: y1 - y0 });
    }
    return out;
  }

  // Split each room edge into shared (interior) and unshared (exterior) segments.
  function wallSegments(rooms) {
    const EPS = 0.08, segs = [];
    const subtract = (lo, hi, cuts) => {
      let parts = [[lo, hi]];
      cuts.forEach(([c0, c1]) => {
        const next = [];
        parts.forEach(([p0, p1]) => {
          if (c1 <= p0 || c0 >= p1) { next.push([p0, p1]); return; }
          if (c0 > p0) next.push([p0, c0]);
          if (c1 < p1) next.push([c1, p1]);
        });
        parts = next;
      });
      return parts.filter(([a, b]) => b - a > 0.05);
    };
    rooms.forEach((r, i) => {
      const others = rooms.filter((_, j) => j !== i);
      const x0 = r.x, y0 = r.y, x1 = r.x + r.width, y1 = r.y + r.height;
      const sides = [
        { axis: "h", at: y0, lo: x0, hi: x1, match: o => Math.abs(o.y + o.height - y0) < EPS, span: o => [o.x, o.x + o.width] },
        { axis: "h", at: y1, lo: x0, hi: x1, match: o => Math.abs(o.y - y1) < EPS, span: o => [o.x, o.x + o.width] },
        { axis: "v", at: x0, lo: y0, hi: y1, match: o => Math.abs(o.x + o.width - x0) < EPS, span: o => [o.y, o.y + o.height] },
        { axis: "v", at: x1, lo: y0, hi: y1, match: o => Math.abs(o.x - x1) < EPS, span: o => [o.y, o.y + o.height] }
      ];
      sides.forEach(sd => {
        const cuts = others.filter(sd.match).map(sd.span);
        const ext = subtract(sd.lo, sd.hi, cuts);
        const push = (a, b, exterior) => segs.push(sd.axis === "h"
          ? { x1: a, y1: sd.at, x2: b, y2: sd.at, exterior, balcony: r.type === "balcony" }
          : { x1: sd.at, y1: a, x2: sd.at, y2: b, exterior, balcony: r.type === "balcony" });
        ext.forEach(([a, b]) => push(a, b, true));
        // shared parts: drawn once (only from the room with the lower index)
        cuts.forEach(([c0, c1]) => {
          const a = Math.max(c0, sd.lo), b = Math.min(c1, sd.hi);
          if (b - a <= 0.05) return;
          const other = others.find(o => sd.match(o) && sd.span(o)[0] === c0 && sd.span(o)[1] === c1);
          if (other && rooms.indexOf(other) < i) return;
          push(a, b, false);
        });
      });
    });
    return segs;
  }

  // Wall placement for a door/window: uses backend wall/position fields when present,
  // otherwise the legacy convention (doors on south wall centre, windows on north wall centre).
  function opening(r, o, defWall) {
    const wall = String(o.wall || o.side || defWall).toLowerCase();
    const w = num(o.width, defWall === "south" ? 3 : 4);
    const horizontal = wall.startsWith("n") || wall.startsWith("s");
    const len = horizontal ? r.width : r.height;
    let off = typeof o.offset === "number" ? o.offset : (len - w) / 2;
    if (typeof o.x === "number" && horizontal) off = o.x - r.x;
    if (typeof o.y === "number" && !horizontal) off = o.y - r.y;
    off = Math.max(0, Math.min(len - w, off));
    if (wall.startsWith("n")) return { ax: r.x + off, ay: r.y, ux: 1, uy: 0, nx: 0, ny: 1, w };
    if (wall.startsWith("s")) return { ax: r.x + off, ay: r.y + r.height, ux: 1, uy: 0, nx: 0, ny: -1, w };
    if (wall.startsWith("w")) return { ax: r.x, ay: r.y + off, ux: 0, uy: 1, nx: 1, ny: 0, w };
    return { ax: r.x + r.width, ay: r.y + off, ux: 0, uy: 1, nx: -1, ny: 0, w };
  }

  // ---------- view ----------
  const MARGIN = { l: 56, r: 32, t: 48, b: 80 };
  function computeFit(st, cw, ch) {
    const B = st.bounds;
    const aw = Math.max(40, cw - MARGIN.l - MARGIN.r), ah = Math.max(40, ch - MARGIN.t - MARGIN.b);
    const s = Math.min(aw / Math.max(1, B.w), ah / Math.max(1, B.h));
    return { s, tx: MARGIN.l + (aw - B.w * s) / 2 - B.x0 * s, ty: MARGIN.t + (ah - B.h * s) / 2 - B.y0 * s };
  }

  function getState(svg) {
    let st = states.get(svg);
    if (st) return st;
    st = { layout: null, opts: {}, view: null, fit: null, userView: false, selected: null, issues: [], onChange: null, raf: 0 };
    states.set(svg, st);

    // pan + click
    let drag = null;
    svg.addEventListener("pointerdown", e => {
      if (e.button !== 0 || !st.view) return;
      drag = { x: e.clientX, y: e.clientY, tx: st.view.tx, ty: st.view.ty, moved: false, id: e.pointerId };
    });
    svg.addEventListener("pointermove", e => {
      if (!drag) return;
      const dx = e.clientX - drag.x, dy = e.clientY - drag.y;
      if (!drag.moved && Math.hypot(dx, dy) < 4) return;
      if (!drag.moved) { drag.moved = true; try { svg.setPointerCapture(drag.id); } catch (_) {} svg.classList.add("panning"); }
      st.view.tx = drag.tx + dx; st.view.ty = drag.ty + dy; st.userView = true;
      schedule(svg, st);
    });
    const end = e => {
      if (!drag) return;
      const wasDrag = drag.moved; drag = null; svg.classList.remove("panning");
      if (wasDrag || e.type !== "pointerup") return;
      const g = e.target && e.target.closest ? e.target.closest("[data-room]") : null;
      if (!g || !st.layout) return;
      const room = st.layout.rooms.find(r => String(r.id) === g.getAttribute("data-room"));
      if (!room) return;
      st.selected = room.id; draw(svg, st);
      if (window.onRoomSelect) window.onRoomSelect(room);
    };
    svg.addEventListener("pointerup", end);
    svg.addEventListener("pointercancel", end);
    svg.addEventListener("wheel", e => {
      if (!st.view) return;
      e.preventDefault();
      const r = svg.getBoundingClientRect();
      zoomAt(svg, st, Math.exp(-e.deltaY * 0.0015), e.clientX - r.left, e.clientY - r.top);
    }, { passive: false });

    const ro = new ResizeObserver(() => {
      if (!st.layout) return;
      const cw = svg.clientWidth, ch = svg.clientHeight;
      if (!cw || !ch) return;
      const nf = computeFit(st, cw, ch);
      if (!st.userView || !st.view) st.view = { ...nf };
      else if (st.fit) { // keep relative zoom & centre on resize
        const k = st.view.s / st.fit.s;
        const cx = (st.lastW / 2 - st.view.tx) / st.view.s, cy = (st.lastH / 2 - st.view.ty) / st.view.s;
        st.view.s = nf.s * k; st.view.tx = cw / 2 - cx * st.view.s; st.view.ty = ch / 2 - cy * st.view.s;
      }
      st.fit = nf; draw(svg, st);
    });
    ro.observe(svg);
    return st;
  }

  function schedule(svg, st) {
    if (st.raf) return;
    st.raf = requestAnimationFrame(() => { st.raf = 0; draw(svg, st); });
  }
  function zoomAt(svg, st, f, cx, cy) {
    if (!st.view || !st.fit) return;
    const s2 = Math.max(st.fit.s * 0.35, Math.min(st.fit.s * 10, st.view.s * f));
    const k = s2 / st.view.s;
    st.view.tx = cx - (cx - st.view.tx) * k; st.view.ty = cy - (cy - st.view.ty) * k; st.view.s = s2;
    st.userView = true; schedule(svg, st);
  }

  // ---------- drawing ----------
  function draw(svg, st) {
    const L = st.layout; if (!L) return;
    const cw = svg.clientWidth, ch = svg.clientHeight;
    if (!cw || !ch) return; // hidden — ResizeObserver redraws when shown
    st.lastW = cw; st.lastH = ch;
    if (!st.fit) st.fit = computeFit(st, cw, ch);
    if (!st.view) st.view = { ...st.fit };
    const { s, tx, ty } = st.view, o = st.opts;
    const X = x => tx + x * s, Y = y => ty + y * s;
    const rooms = L.rooms || [];

    while (svg.firstChild) svg.removeChild(svg.firstChild);
    svg.setAttribute("viewBox", `0 0 ${cw} ${ch}`);
    svg.setAttribute("width", cw); svg.setAttribute("height", ch);
    svg.setAttribute("font-family", SANS);

    const defs = el("defs", null, svg);
    const pat = el("pattern", { id: "pv-warn", width: 6, height: 6, patternUnits: "userSpaceOnUse", patternTransform: "rotate(45)" }, defs);
    el("line", { x1: 0, y1: 0, x2: 0, y2: 6, stroke: C.warn, "stroke-width": 2, opacity: 0.55 }, pat);

    el("rect", { x: 0, y: 0, width: cw, height: ch, fill: C.paper }, svg);

    // grid (screen space, 1 ft minor when legible, 5 ft major)
    const grid = el("g", { "shape-rendering": "crispEdges" }, svg);
    const wx0 = Math.floor(-tx / s), wx1 = Math.ceil((cw - tx) / s), wy0 = Math.floor(-ty / s), wy1 = Math.ceil((ch - ty) / s);
    const minor = s >= 9 ? 1 : 5, major = s >= 9 ? 5 : 10;
    for (let x = Math.ceil(wx0 / minor) * minor; x <= wx1; x += minor)
      el("line", { x1: X(x), y1: 0, x2: X(x), y2: ch, stroke: x % major === 0 ? C.gridMajor : C.grid, "stroke-width": 1 }, grid);
    for (let y = Math.ceil(wy0 / minor) * minor; y <= wy1; y += minor)
      el("line", { x1: 0, y1: Y(y), x2: cw, y2: Y(y), stroke: y % major === 0 ? C.gridMajor : C.grid, "stroke-width": 1 }, grid);

    // ---- world layer ----
    const W = el("g", { transform: `matrix(${s} 0 0 ${s} ${tx} ${ty})` }, svg);
    const NSS = { "vector-effect": "non-scaling-stroke" };

    rooms.forEach(r => {
      const c = ROOM[r.type] || { fill: "#F1EFEA", text: "#3A352F" };
      const g = el("g", { "data-room": r.id, class: "plan-room" }, W);
      el("rect", { x: r.x, y: r.y, width: r.width, height: r.height, fill: c.fill, class: "room-fill" }, g);
      const area = num(r.area, r.width * r.height);
      title(g, `${r.label || prettyType(r.type)} — ${fmt(r.width)} × ${fmt(r.height)} ft · ${area.toFixed(0)} sqft`);
      if (o.furniture) (r.furniture || []).forEach(f => {
        const fr = el("rect", { x: f.x, y: f.y, width: f.width, height: f.height, rx: Math.min(0.35, f.width / 4, f.height / 4), fill: C.furnFill, stroke: C.furnStroke, "stroke-width": 1, ...NSS, class: "furn" }, g);
        title(fr, `${prettyType(f.type)} · ${fmt(f.width)} × ${fmt(f.height)} ft`);
      });
    });

    // backend geometry problems: hatched, reported, not hidden
    st.issues.forEach(i => el("rect", { x: i.x, y: i.y, width: i.w, height: i.h, fill: "url(#pv-warn)", stroke: C.warn, "stroke-width": 1.5, ...NSS }, W));

    // plumbing routes (world geometry, constant stroke)
    if (o.plumbing) (L.plumbing_routes || []).forEach(rt => {
      const p = rt.path || []; if (p.length < 2) return;
      const dr = rt.kind === "drainage";
      el("polyline", { points: p.map(q => q.join(",")).join(" "), fill: "none", stroke: dr ? C.drain : C.water, "stroke-width": 1.6, "stroke-dasharray": dr ? "5 3" : "8 3", "stroke-linecap": "round", "stroke-linejoin": "round", opacity: 0.9, ...NSS, "pointer-events": "none" }, W);
    });

    // walls
    const wallG = el("g", { "pointer-events": "none", "stroke-linecap": "square" }, W);
    wallSegments(rooms).forEach(sg => {
      const ext = sg.exterior && !sg.balcony;
      el("line", { x1: sg.x1, y1: sg.y1, x2: sg.x2, y2: sg.y2, stroke: ext ? C.extWall : C.intWall,
        "stroke-width": ext ? Math.max(3, Math.min(6, s * 0.5)) : Math.max(1.5, Math.min(3, s * 0.25)),
        "stroke-dasharray": sg.balcony && sg.exterior ? "4 3" : "none", ...NSS }, wallG);
    });

    // openings
    const openG = el("g", { "pointer-events": "none" }, W);
    rooms.forEach(r => {
      (r.windows || []).forEach(w => {
        const a = opening(r, w, "north"), bx = a.ax + a.ux * a.w, by = a.ay + a.uy * a.w;
        el("line", { x1: a.ax, y1: a.ay, x2: bx, y2: by, stroke: C.paper, "stroke-width": 6, ...NSS }, openG);
        el("line", { x1: a.ax, y1: a.ay, x2: bx, y2: by, stroke: C.window, "stroke-width": 4, ...NSS }, openG);
        el("line", { x1: a.ax, y1: a.ay, x2: bx, y2: by, stroke: "#FFFFFF", "stroke-width": 1, ...NSS }, openG);
      });
      (r.doors || []).forEach(d => {
        const a = opening(r, d, "south"), bx = a.ax + a.ux * a.w, by = a.ay + a.uy * a.w;
        const lx = a.ax + a.nx * a.w, ly = a.ay + a.ny * a.w;
        const sweep = (a.nx * a.uy - a.ny * a.ux) > 0 ? 1 : 0;
        el("line", { x1: a.ax, y1: a.ay, x2: bx, y2: by, stroke: C.paper, "stroke-width": 7, ...NSS }, openG);
        el("line", { x1: a.ax, y1: a.ay, x2: lx, y2: ly, stroke: C.extWall, "stroke-width": 1.4, ...NSS }, openG);
        el("path", { d: `M ${lx} ${ly} A ${a.w} ${a.w} 0 0 ${sweep} ${bx} ${by}`, fill: "none", stroke: C.intWall, "stroke-width": 0.9, "stroke-dasharray": "3 2", ...NSS }, openG);
      });
    });

    // selection outline
    const sel = rooms.find(r => r.id === st.selected);
    if (sel) el("rect", { x: sel.x, y: sel.y, width: sel.width, height: sel.height, fill: "none", stroke: C.select, "stroke-width": 2.5, ...NSS, "pointer-events": "none" }, W);

    // ---- screen layer ----
    const S = el("g", { "pointer-events": "none" }, svg);
    const occupied = [];

    // lighting markers: fixed pixel size
    if (o.lighting) rooms.forEach(r => (r.lighting || []).forEach(l => {
      const g = el("g", { transform: `translate(${X(l.x)},${Y(l.y)})` }, S);
      const rad = l.type === "pendant_light" ? 4.2 : 3.4;
      el("circle", { r: rad, fill: "#FCE7A4", stroke: C.light, "stroke-width": 1.2 }, g);
      el("path", { d: `M ${-rad + 1} 0 H ${rad - 1} M 0 ${-rad + 1} V ${rad - 1}`, stroke: C.light, "stroke-width": 0.9 }, g);
    }));

    // plumbing fixtures
    const fixtures = o.plumbing ? (L.plumbing_fixtures || []) : [];
    fixtures.forEach(fx => {
      const col = fx.type === "toilet" ? C.drain : C.water;
      el("circle", { cx: X(fx.x), cy: Y(fx.y), r: 4, fill: "#FFFFFF", stroke: col, "stroke-width": 1.4 }, S);
      el("circle", { cx: X(fx.x), cy: Y(fx.y), r: 1.7, fill: col }, S);
    });

    // room labels — fit-tested against each room's on-screen box
    rooms.forEach(r => {
      const c = ROOM[r.type] || { text: "#3A352F" };
      const box = { x: X(r.x) + 5, y: Y(r.y) + 5, w: r.width * s - 10, h: r.height * s - 10 };
      if (box.w < 18 || box.h < 10) return;
      const cx = box.x + box.w / 2, cy = box.y + box.h / 2;
      const g = el("g", null, S);
      const bg = el("rect", { rx: 3, fill: C.paper, opacity: 0.88 }, g);
      const name = String(r.label || prettyType(r.type));
      const t = el("text", { x: cx, "text-anchor": "middle", "font-weight": 700, fill: c.text, "letter-spacing": "0.06em" }, g);
      const tries = [[name, 12.5], [name, 11], [SHORT[r.type] ? name.replace(new RegExp("^" + prettyType(r.type), "i"), SHORT[r.type]).trim() : name, 10.5], [SHORT[r.type] || name, 9.5]];
      let ok = null;
      for (const [txt, fs] of tries) {
        t.textContent = txt.toUpperCase(); t.setAttribute("font-size", fs);
        const tw = textWidth(t, fs);
        if (tw <= box.w && fs + 2 <= box.h) { ok = { fs, tw }; break; }
      }
      if (!ok) { S.removeChild(g); return; }
      let dimTxt = null, dw = 0;
      const dfs = 10;
      if (o.dimensions && box.h >= ok.fs + dfs + 10) {
        const d = el("text", { x: cx, "text-anchor": "middle", "font-size": dfs, "font-family": MONO, fill: C.dim }, g);
        const area = num(r.area, r.width * r.height);
        for (const txt of [`${fmt(r.width)} × ${fmt(r.height)} ft · ${area.toFixed(0)} sqft`, `${fmt(r.width)} × ${fmt(r.height)}`]) {
          d.textContent = txt; dw = textWidth(d, dfs, true);
          if (dw <= box.w) { dimTxt = d; break; }
        }
        if (!dimTxt) g.removeChild(d);
      }
      const blockH = ok.fs + (dimTxt ? dfs + 4 : 0);
      const top = cy - blockH / 2;
      t.setAttribute("y", top + ok.fs * 0.82);
      if (dimTxt) dimTxt.setAttribute("y", top + ok.fs + 4 + dfs * 0.8);
      const bw = Math.max(ok.tw, dw) + 10, rect = { x: cx - bw / 2, y: top - 3, w: bw, h: blockH + 6 };
      bg.setAttribute("x", rect.x); bg.setAttribute("y", rect.y); bg.setAttribute("width", rect.w); bg.setAttribute("height", rect.h);
      occupied.push(rect);
    });

    // furniture labels: only for the selected room, only when they fit and don't collide
    if (o.furniture && sel) (sel.furniture || []).forEach(f => {
      const fw = f.width * s, fh = f.height * s; if (fh < 11) return;
      const t = el("text", { x: X(f.x + f.width / 2), y: Y(f.y + f.height / 2) + 3.2, "text-anchor": "middle", "font-size": 9, fill: "#3A352F", "font-weight": 600 }, S);
      t.textContent = prettyType(f.type);
      const tw = textWidth(t, 9), rect = { x: X(f.x + f.width / 2) - tw / 2, y: Y(f.y + f.height / 2) - 6, w: tw, h: 12 };
      if (tw > fw - 4 || occupied.some(q => hit(q, rect))) S.removeChild(t); else occupied.push(rect);
    });

    // fixture tags only when zoomed in enough, never over a room label
    if (s >= 16) fixtures.forEach(fx => {
      const lbl = fx.type === "toilet" ? "WC" : fx.type === "washbasin" ? "WB" : fx.type === "shower" ? "SH" : "SK";
      const rect = { x: X(fx.x) - 8, y: Y(fx.y) - 17, w: 16, h: 10 };
      if (occupied.some(q => hit(q, rect))) return;
      const t = el("text", { x: X(fx.x), y: Y(fx.y) - 8, "text-anchor": "middle", "font-size": 8.5, "font-family": MONO, "font-weight": 700, fill: fx.type === "toilet" ? C.drain : C.water }, S);
      t.textContent = lbl; occupied.push(rect);
    });

    // overall dimension lines
    const B = st.bounds;
    if (o.dimensions) {
      const dg = el("g", { stroke: C.dim, "stroke-width": 1 }, S);
      const yb = Y(B.y1) + 20, xl = X(B.x0) - 22;
      el("line", { x1: X(B.x0), y1: yb, x2: X(B.x1), y2: yb }, dg);
      [X(B.x0), X(B.x1)].forEach(x => el("line", { x1: x, y1: yb - 5, x2: x, y2: yb + 5 }, dg));
      el("line", { x1: xl, y1: Y(B.y0), x2: xl, y2: Y(B.y1) }, dg);
      [Y(B.y0), Y(B.y1)].forEach(y => el("line", { x1: xl - 5, y1: y, x2: xl + 5, y2: y }, dg));
      const tb = el("text", { x: (X(B.x0) + X(B.x1)) / 2, y: yb + 15, "text-anchor": "middle", "font-size": 11, "font-family": MONO, "font-weight": 600, fill: C.dim }, S);
      tb.textContent = `${fmt(B.w)} ft`;
      const lx = xl - 8, ly = (Y(B.y0) + Y(B.y1)) / 2;
      const tl = el("text", { x: lx, y: ly, "text-anchor": "middle", "font-size": 11, "font-family": MONO, "font-weight": 600, fill: C.dim, transform: `rotate(-90 ${lx} ${ly})` }, S);
      tl.textContent = `${fmt(B.h)} ft`;
    }

    // ---- fixed chrome (always readable, outside the plan) ----
    const chrome = el("g", null, svg);
    // title
    const meta = `${String(L.metadata?.style || "modern").toUpperCase()} · ${num(L.built_up_area).toFixed(0)} SQFT · ${String(L.orientation?.requested_direction || "").replace(/_/g, " ").toUpperCase() || "—"} FACING`;
    const tt = el("text", { x: 16, y: 24, "font-size": 10, "font-family": MONO, "letter-spacing": "0.1em", fill: C.dim, "font-weight": 600 }, chrome);
    tt.textContent = meta;
    const ttw = textWidth(tt, 10, true);
    chrome.insertBefore(el("rect", { x: 10, y: 11, width: ttw + 12, height: 19, rx: 4, fill: C.paper, stroke: "#E2DBCF" }), tt);

    // compass (north is up in the layout's coordinate system)
    const cg = el("g", { transform: `translate(${cw - 30},${30})` }, chrome);
    el("circle", { r: 15, fill: C.paper, stroke: C.dim, "stroke-width": 1 }, cg);
    el("path", { d: "M 0 -11 L 3.5 2 L 0 0 L -3.5 2 Z", fill: C.select }, cg);
    const nt = el("text", { y: 11, "text-anchor": "middle", "font-size": 8, "font-weight": 800, fill: C.extWall }, cg); nt.textContent = "N";

    // scale bar
    const steps = [1, 2, 5, 10, 20, 50, 100];
    const len = steps.find(v => v * s >= 70) || 100, px = len * s;
    const sb = el("g", { transform: `translate(16,${ch - 20})` }, chrome);
    el("rect", { x: -6, y: -16, width: px + 52, height: 26, rx: 4, fill: C.paper, opacity: 0.9 }, sb);
    el("rect", { x: 0, y: -3, width: px / 2, height: 4, fill: C.extWall }, sb);
    el("rect", { x: px / 2, y: -3, width: px / 2, height: 4, fill: C.paper, stroke: C.extWall, "stroke-width": 1 }, sb);
    const st1 = el("text", { x: 0, y: -7, "font-size": 9, "font-family": MONO, fill: C.dim }, sb); st1.textContent = "0";
    const st2 = el("text", { x: px + 4, y: 2, "font-size": 9, "font-family": MONO, fill: C.dim }, sb); st2.textContent = `${len} ft`;

    // legend (only enabled layers)
    const items = [["wall", C.extWall, "Exterior wall"]];
    if (o.plumbing) items.push(["line", C.water, "Water supply"], ["dash", C.drain, "Drainage"]);
    if (o.lighting) items.push(["dot", C.light, "Light"]);
    if (o.furniture) items.push(["box", C.furnStroke, "Furniture"]);
    if (st.issues.length) items.push(["box", C.warn, "Overlap (backend)"]);
    const lg = el("g", null, chrome);
    let lx2 = 0; const parts = [];
    items.forEach(([kind, col, label]) => {
      const g = el("g", null, lg);
      if (kind === "wall") el("rect", { x: 0, y: -2.5, width: 14, height: 5, fill: col }, g);
      if (kind === "line" || kind === "dash") el("line", { x1: 0, y1: 0, x2: 14, y2: 0, stroke: col, "stroke-width": 2, "stroke-dasharray": kind === "dash" ? "4 2" : "none" }, g);
      if (kind === "dot") el("circle", { cx: 7, cy: 0, r: 3.5, fill: "#FCE7A4", stroke: col, "stroke-width": 1.2 }, g);
      if (kind === "box") el("rect", { x: 2, y: -4, width: 10, height: 8, fill: "none", stroke: col, "stroke-width": 1.2 }, g);
      const t = el("text", { x: 18, y: 3.5, "font-size": 10, fill: C.dim, "font-weight": 600 }, g); t.textContent = label;
      parts.push({ g, w: 22 + textWidth(t, 10) });
    });
    const totalW = parts.reduce((a, p) => a + p.w + 8, 0);
    const legendX = Math.max(16 + px + 60, cw - totalW - 16);
    parts.forEach(p => { p.g.setAttribute("transform", `translate(${legendX + lx2},${ch - 21})`); lx2 += p.w + 8; });
    lg.insertBefore(el("rect", { x: legendX - 8, y: ch - 34, width: totalW + 8, height: 26, rx: 4, fill: C.paper, opacity: 0.9 }), lg.firstChild);

    if (st.onChange) st.onChange(st.view.s / st.fit.s);
  }

  // ---------- public API (renderPlan signature preserved) ----------
  function renderPlan(svg, layout, opts) {
    if (!layout || !layout.rooms || !layout.rooms.length) return;
    svg.removeAttribute("hidden");
    const st = getState(svg);
    if (st.layout !== layout) {
      st.layout = layout; st.bounds = bounds(layout); st.issues = findOverlaps(layout.rooms);
      st.view = null; st.fit = null; st.userView = false; st.selected = layout.rooms[0] ? layout.rooms[0].id : null;
      if (st.issues.length) console.warn("[IntelliTwin] Backend layout has overlapping rooms:", st.issues);
    }
    st.opts = Object.assign({ furniture: true, lighting: true, plumbing: true, dimensions: true }, opts || {});
    draw(svg, st);
  }

  const PlanView = {
    zoomBy(svg, f) { const st = getState(svg); zoomAt(svg, st, f, svg.clientWidth / 2, svg.clientHeight / 2); },
    fit(svg) { const st = getState(svg); if (!st.layout) return; st.fit = computeFit(st, svg.clientWidth, svg.clientHeight); st.view = { ...st.fit }; st.userView = false; draw(svg, st); },
    select(svg, id) { const st = getState(svg); st.selected = id; draw(svg, st); },
    zoom(svg) { const st = getState(svg); return st.view && st.fit ? st.view.s / st.fit.s : 1; },
    issues(svg) { return getState(svg).issues.slice(); },
    onChange(svg, cb) { getState(svg).onChange = cb; }
  };

  window.renderPlan = renderPlan;
  window.PlanView = PlanView;
})();
