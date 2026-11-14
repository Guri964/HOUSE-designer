import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";

// All coordinates remain in backend feet. No generated placements are moved.
let scene,
  camera,
  renderer,
  controls,
  observer,
  model,
  floors,
  walls,
  furniture,
  markers,
  plumbing,
  openings,
  illumination,
  selection,
  ambient,
  hemi,
  sun,
  environmentTarget,
  ground;
let layoutRef,
  selectedId,
  generation = 0,
  frame = 0,
  lastTime = 0,
  pointerStart;
let mode = "morning",
  cutaway = true,
  fitted = true;
const visibility = {
  walls: true,
  furniture: true,
  lighting: true,
  plumbing: true,
};
const assets = new Map(),
  loader = new GLTFLoader();
const palette = {
  plaster: "#e9e7e1",
  exterior: "#dbdfdc",
  stone: "#d7d8d4",
  wood: "#c2a17a",
  tile: "#bac8c8",
  ground: "#818d92",
  selection: "#36d8cf",
};
const MODES = {
  morning: {
    bg: "#b8c7ce",
    sky: "#f6f3e7",
    ground: "#7b8997",
    sun: "#ffebc4",
    ambient: 0.38,
    hemi: 1.5,
    power: 2.5,
    exposure: 1.05,
    local: 35,
    light: "#fff0d4",
    direction: [-1, 1.6, -0.8],
  },
  neon: {
    bg: "#242c3a",
    sky: "#adb9d8",
    ground: "#45465e",
    sun: "#9baed2",
    ambient: 0.4,
    hemi: 0.85,
    power: 0.6,
    exposure: 1.08,
    local: 100,
    light: "#7ebde3",
    direction: [-1, 1.6, -0.8],
  },
  evening: {
    bg: "#92979c",
    sky: "#ffe3c1",
    ground: "#7e7780",
    sun: "#ffb36e",
    ambient: 0.35,
    hemi: 1.15,
    power: 2.2,
    exposure: 1,
    local: 65,
    light: "#ffd293",
    direction: [-1, 0.7, 0.6],
  },
  night: {
    bg: "#283441",
    sky: "#a3b5cf",
    ground: "#485366",
    sun: "#b6ccec",
    ambient: 0.38,
    hemi: 0.75,
    power: 0.35,
    exposure: 1.15,
    local: 100,
    light: "#ffdaab",
    direction: [0.4, 1.6, -1],
  },
};
const modelNames = {
  bed: "bedDouble",
  sofa: "loungeSofa",
  sofa_single: "loungeChair",
  coffee_table: "tableCoffee",
  tv_unit: "cabinetTelevision",
  counter: "kitchenCabinet",
  refrigerator: "kitchenFridge",
  dining_table: "table",
  chair: "chair",
  study_table: "desk",
  wardrobe: "bookcaseClosed",
  cabinet: "cabinetTelevision",
  side_table: "sideTable",
  table_small: "sideTable",
  toilet: "toilet",
  washbasin: "bathroomSink",
  shower: "shower",
  kitchen_sink: "kitchenSink",
};
const objectHeights = {
  bed: 2,
  sofa: 2.7,
  sofa_single: 2.7,
  coffee_table: 1.3,
  tv_unit: 2,
  counter: 2.85,
  refrigerator: 5.6,
  dining_table: 2.5,
  chair: 3,
  study_table: 2.5,
  wardrobe: 5.8,
  cabinet: 2.6,
  side_table: 1.8,
  table_small: 1.8,
  toilet: 2.4,
  washbasin: 2.8,
  shower: 6.6,
  kitchen_sink: 2.85,
};

// Floor-to-floor height used when stacking multiple floors in the 3D twin.
const STORY_HEIGHT = 10;
const clip = new THREE.Plane(new THREE.Vector3(0, -1, 0), 2.65);
const textures = new Set();
function texture(kind, width = 4, height = 4) {
  const c = document.createElement("canvas");
  c.width = c.height = 256;
  const x = c.getContext("2d");
  x.fillStyle =
    kind === "wood"
      ? "#cab18c"
      : kind === "tile"
        ? "#c8d4d3"
        : kind === "plaster"
          ? "#f4f3ef"
          : "#e0e2df";
  x.fillRect(0, 0, 256, 256);
  let seed = 41;
  const rand = () => {
    seed = (seed * 16807) % 2147483647;
    return seed / 2147483647;
  };
  for (let i = 0; i < 2400; i++) {
    x.fillStyle = `rgba(80,85,80,${rand() * 0.035})`;
    x.fillRect(rand() * 256, rand() * 256, kind === "wood" ? 40 : 2, 1);
  }
  if (kind === "wood") {
    for (let j = 0; j < 4; j++) {
      x.fillStyle = "#a99274";
      x.fillRect(0, j * 64, 256, 1);
      x.fillRect(j % 2 ? 75 : 175, j * 64, 1, 64);
    }
  } else if (kind !== "plaster") {
    x.strokeStyle = kind === "tile" ? "#aebfbe" : "#c9cdca";
    x.lineWidth = 2;
    x.strokeRect(0, 0, 256, 256);
  }
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  t.wrapS = t.wrapT = THREE.RepeatWrapping;
  t.repeat.set(width / 4, height / 4);
  t.anisotropy = 4;
  textures.add(t);
  return t;
}
function material(color, roughness = 0.8, extra = {}) {
  return new THREE.MeshStandardMaterial({
    color,
    roughness,
    metalness: 0,
    ...extra,
  });
}
function box(group, w, h, d, x, y, z, mat) {
  const m = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), mat);
  m.position.set(x, y, z);
  m.castShadow = true;
  m.receiveShadow = true;
  group.add(m);
  return m;
}
function initThree() {
  if (renderer) return;
  const canvas = document.getElementById("threeCanvas"),
    host = document.getElementById("threeContainer");
  if (!canvas || !host) return;
  renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
  renderer.setPixelRatio(Math.min(devicePixelRatio, 1.5));
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  renderer.localClippingEnabled = true;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  scene = new THREE.Scene();
  scene.background = new THREE.Color(MODES[mode].bg);
  camera = new THREE.PerspectiveCamera(38, 1, 0.1, 1000);
  controls = new OrbitControls(camera, canvas);
  controls.enableDamping = true;
  controls.dampingFactor = 0.09;
  controls.maxPolarAngle = Math.PI / 2.05;
  controls.addEventListener("start", () => (fitted = false));
  ambient = new THREE.AmbientLight();
  hemi = new THREE.HemisphereLight();
  sun = new THREE.DirectionalLight();
  sun.castShadow = true;
  sun.shadow.mapSize.set(2048, 2048);
  sun.shadow.normalBias = 0.04;
  sun.shadow.bias = -0.0001;
  sun.shadow.radius = 3;
  scene.add(ambient, hemi, sun, sun.target);
  const env = new RoomEnvironment();
  const pmrem = new THREE.PMREMGenerator(renderer);
  environmentTarget = pmrem.fromScene(env, 0.04);
  scene.environment = environmentTarget.texture;
  env.dispose();
  pmrem.dispose();
  ground = new THREE.Mesh(
    new THREE.PlaneGeometry(1000, 1000),
    material(palette.ground, 0.95, { map: texture("plaster", 100, 100) }),
  );
  ground.rotation.x = -Math.PI / 2;
  ground.position.y = -0.52;
  ground.receiveShadow = true;
  scene.add(ground);
  model = new THREE.Group();
  scene.add(model);
  canvas.addEventListener("pointerdown", onPointerDown);
  canvas.addEventListener("pointerup", onPointerUp);
  window.addEventListener("resize", resize);
  window.addEventListener("keydown", onKey);
  window.addEventListener("pagehide", disposeThree);
  observer = new ResizeObserver(resize);
  observer.observe(host);
  resize();
  updateLighting(1);
  frame = requestAnimationFrame(animate);
}
function onKey(e) {
  if (e.target.matches("input,textarea,select")) return;
  if (e.key.toLowerCase() === "r") resetCamera();
}
function onPointerDown(e) {
  pointerStart = { x: e.clientX, y: e.clientY, button: e.button };
}
function onPointerUp(e) {
  if (
    !pointerStart ||
    pointerStart.button !== 0 ||
    Math.hypot(e.clientX - pointerStart.x, e.clientY - pointerStart.y) > 5 ||
    !floors
  )
    return;
  const rect = renderer.domElement.getBoundingClientRect();
  const ray = new THREE.Raycaster();
  ray.setFromCamera(
    new THREE.Vector2(
      ((e.clientX - rect.left) / rect.width) * 2 - 1,
      (-(e.clientY - rect.top) / rect.height) * 2 + 1,
    ),
    camera,
  );
  const hits = ray.intersectObjects(floors.children);
  if (hits.length) {
    const r = hits[0].object.userData.room;
    selectRoom(r.id);
    window.onRoomSelect?.(r);
  }
}
function resize() {
  if (!renderer) return;
  const host = document.getElementById("threeContainer");
  if (!host.clientWidth || !host.clientHeight) return;
  renderer.setSize(host.clientWidth, host.clientHeight, false);
  camera.aspect = host.clientWidth / host.clientHeight;
  camera.updateProjectionMatrix();
  if (fitted && layoutRef) fitCamera();
}
function animate(time) {
  frame = requestAnimationFrame(animate);
  const dt = Math.min((time - lastTime) / 1000, 0.15);
  lastTime = time;
  updateLighting(
    window.matchMedia("(prefers-reduced-motion: reduce)").matches
      ? 1
      : 1 - Math.exp(-7 * dt),
  );
  controls.update(dt);
  if (!document.hidden) renderer.render(scene, camera);
}
function updateLighting(a) {
  if (!scene) return;
  const p = MODES[mode];
  const mix = (light, col, power) => {
    light.color.lerp(new THREE.Color(col), a);
    light.intensity = THREE.MathUtils.lerp(light.intensity, power, a);
  };
  scene.background.lerp(new THREE.Color(p.bg), a);
  ground.material.color.lerp(
    new THREE.Color(
      mode === "morning"
        ? "#818d92"
        : mode === "evening"
          ? "#6e737b"
          : "#273340",
    ),
    a,
  );
  ground.material.envMapIntensity = mode === "morning" ? 0.25 : 0.04;
  mix(ambient, p.sky, p.ambient);
  mix(hemi, p.sky, p.hemi);
  hemi.groundColor.lerp(new THREE.Color(p.ground), a);
  mix(sun, p.sun, p.power);
  renderer.toneMappingExposure = THREE.MathUtils.lerp(
    renderer.toneMappingExposure,
    p.exposure,
    a,
  );
  if (layoutRef) {
    const b = bounds(),
      center = b.getCenter(new THREE.Vector3()),
      radius = b.getSize(new THREE.Vector3()).length() / 2;
    sun.position.lerp(
      center
        .clone()
        .add(new THREE.Vector3(...p.direction).multiplyScalar(radius + 10)),
      a,
    );
    sun.target.position.copy(center);
    sun.target.updateMatrixWorld();
  }
  illumination?.children.forEach((l, i) => {
    mix(
      l,
      mode === "neon" ? (i % 3 === 0 ? "#bca1ea" : "#77d6df") : p.light,
      p.local,
    );
  });
  markers?.traverse((o) => {
    if (o.material?.emissive) {
      o.material.emissive.lerp(new THREE.Color(p.light), a);
    }
  });
}
function setLightingMode(value) {
  if (!MODES[value]) return;
  mode = value;
}
function disposeTree(group) {
  const geometries = new Set(),
    materials = new Set();
  group.traverse((o) => {
    if (o.geometry) geometries.add(o.geometry);
    if (o.material)
      (Array.isArray(o.material) ? o.material : [o.material]).forEach((m) =>
        materials.add(m),
      );
  });
  geometries.forEach((g) => g.dispose());
  materials.forEach((m) => m.dispose());
}
function clearModel() {
  if (!model) return;
  disposeTree(model);
  model.clear();
  const groundMap = ground?.material.map;
  textures.forEach((t) => {
    if (t !== groundMap) {
      t.dispose();
      textures.delete(t);
    }
  });
}

function wallSegments(rooms) {
  const EPS = 0.08,
    segs = [];
  const subtract = (lo, hi, cuts) => {
    let parts = [[lo, hi]];
    cuts.forEach(([c0, c1]) => {
      const next = [];
      parts.forEach(([p0, p1]) => {
        if (c1 <= p0 || c0 >= p1) {
          next.push([p0, p1]);
          return;
        }
        if (c0 > p0) next.push([p0, c0]);
        if (c1 < p1) next.push([c1, p1]);
      });
      parts = next;
    });
    return parts.filter(([x, y]) => y - x > 0.05);
  };
  rooms.forEach((r, i) => {
    const others = rooms.filter((_, j) => j !== i);
    const x0 = r.x,
      y0 = r.y,
      x1 = r.x + r.width,
      y1 = r.y + r.height;
    const sides = [
      {
        h: true,
        at: y0,
        lo: x0,
        hi: x1,
        match: (o) => Math.abs(o.y + o.height - y0) < EPS,
        span: (o) => [o.x, o.x + o.width],
      },
      {
        h: true,
        at: y1,
        lo: x0,
        hi: x1,
        match: (o) => Math.abs(o.y - y1) < EPS,
        span: (o) => [o.x, o.x + o.width],
      },
      {
        h: false,
        at: x0,
        lo: y0,
        hi: y1,
        match: (o) => Math.abs(o.x + o.width - x0) < EPS,
        span: (o) => [o.y, o.y + o.height],
      },
      {
        h: false,
        at: x1,
        lo: y0,
        hi: y1,
        match: (o) => Math.abs(o.x - x1) < EPS,
        span: (o) => [o.y, o.y + o.height],
      },
    ];
    sides.forEach((sd) => {
      const adj = others.filter(sd.match);
      const push = (a, b, exterior) =>
        segs.push({
          h: sd.h,
          at: sd.at,
          a,
          b,
          exterior,
          balcony: r.type === "balcony",
        });
      subtract(sd.lo, sd.hi, adj.map(sd.span)).forEach(([a, b]) =>
        push(a, b, true),
      );
      adj.forEach((o) => {
        if (rooms.indexOf(o) < i) return;
        const [c0, c1] = sd.span(o),
          a = Math.max(c0, sd.lo),
          b = Math.min(c1, sd.hi);
        if (b - a > 0.05)
          push(a, b, o.type === "balcony" && r.type === "balcony");
      });
    });
  });
  return segs;
}

function bounds() {
  const b = new THREE.Box3();
  const floorPlans = layoutRef?.floor_plans || [
    { rooms: layoutRef?.rooms || [] },
  ];
  floorPlans.forEach((plan, fi) => {
    const yOff = fi * STORY_HEIGHT;
    // Exterior walls extend to STORY_HEIGHT in multi-floor; use that for bounds
    const topY = yOff + (layoutRef?.floors && layoutRef.floors > 1 ? STORY_HEIGHT : 7.2);
    (plan.rooms || []).forEach((r) => {
      b.expandByPoint(new THREE.Vector3(r.x, yOff, r.y));
      b.expandByPoint(
        new THREE.Vector3(r.x + r.width, topY, r.y + r.height),
      );
    });
  });
  return b.isEmpty()
    ? new THREE.Box3(new THREE.Vector3(0, 0, 0), new THREE.Vector3(40, 7.2, 40))
    : b;
}
function openingPosition(r, o) {
  const side = String(o.wall || o.side || o.direction || "").toLowerCase();
  const sides = { top: "north", bottom: "south", left: "west", right: "east" };
  const s = sides[side] || side;
  if (!["north", "south", "east", "west"].includes(s)) return null;
  const horizontal = s === "north" || s === "south",
    span = horizontal ? r.width : r.height;
  const offset = Number.isFinite(o.offset)
    ? o.offset
    : typeof o.position === "number"
      ? o.position
      : null;
  const pos = o.position && typeof o.position === "object" ? o.position : o;
  const coord = horizontal ? pos.x : pos.y;
  const middle = Number.isFinite(coord)
    ? coord
    : offset !== null
      ? (horizontal ? r.x : r.y) + offset
      : null;
  if (middle === null) return null;
  const width = Math.min(o.width || 3, span);
  const start = horizontal ? r.x : r.y;
  if (middle - width / 2 < start || middle + width / 2 > start + span)
    return null;
  return {
    h: horizontal,
    at:
      s === "north"
        ? r.y
        : s === "south"
          ? r.y + r.height
          : s === "west"
            ? r.x
            : r.x + r.width,
    a: middle - width / 2,
    b: middle + width / 2,
    kind: o.kind,
    sill: o.kind === "window" ? 2.8 : 0,
    head: o.kind === "window" ? 5.8 : 6.4,
  };
}
function buildFromLayout(layout, opts = {}) {
  initThree();
  if (!renderer) return;
  generation++;
  const token = generation;
  clearModel();
  layoutRef = layout;
  floors = new THREE.Group();
  walls = new THREE.Group();
  furniture = new THREE.Group();
  markers = new THREE.Group();
  plumbing = new THREE.Group();
  openings = new THREE.Group();
  illumination = new THREE.Group();
  selection = new THREE.Group();
  model.add(
    floors,
    walls,
    furniture,
    markers,
    plumbing,
    openings,
    illumination,
    selection,
  );
  const style = opts.style || layout.metadata?.style || "modern",
    apertures = [];
  const floorPlans = layout.floor_plans || [
    {
      rooms: layout.rooms || [],
      furniture: layout.furniture || [],
      lighting: layout.lighting || [],
      plumbing_fixtures: layout.plumbing_fixtures || [],
      plumbing_routes: layout.plumbing_routes || [],
    },
  ];
  // Structural slab material (concrete, visible between rooms and at edges)
  const slabMat = material("#8d8782", 0.85);

  floorPlans.forEach((plan, fi) => {
    const yOff = fi * STORY_HEIGHT;
    const stairRoom = plan.rooms.find((r) => r.type === "staircase");

    // ---- Continuous full-building floor slab (structural) ----
    // Covers the entire footprint so floors look like connected slabs,
    // not separate floating platforms. On upper floors with a staircase,
    // the slab is split into strips around the stair opening.
    if (fi > 0 && stairRoom) {
      const s = stairRoom;
      const Wb = layout.width, Hb = layout.height;
      const cz = Hb / 2;
      // Left strip (x: 0 → s.x)
      if (s.x > 0.1) box(floors, s.x, 0.18, Hb, s.x / 2, yOff - 0.09, cz, slabMat);
      // Right strip (x: s.x+s.width → Wb)
      const rightStart = s.x + s.width;
      if (rightStart < Wb - 0.1) box(floors, Wb - rightStart, 0.18, Hb, rightStart + (Wb - rightStart) / 2, yOff - 0.09, cz, slabMat);
      // Back strip (z: s.height → Hb, only under stair x-range)
      if (s.height < Hb - 0.1) box(floors, s.width, 0.18, Hb - s.height, s.x + s.width / 2, yOff - 0.09, s.height + (Hb - s.height) / 2, slabMat);
    } else {
      // No stair opening: single full slab
      box(floors, layout.width, 0.18, layout.height, layout.width / 2, yOff - 0.09, layout.height / 2, slabMat);
    }

    (plan.rooms || []).forEach((r) => {
      // On upper floors, skip the floor slab for the staircase room:
      // that area is an opening (void) where the flight from below comes up.
      if (r.type === "staircase" && fi > 0) return;
      const kind =
        r.type === "bedroom" || style === "traditional"
          ? "wood"
          : r.type === "bathroom" || r.type === "balcony"
            ? "tile"
            : r.type === "staircase"
              ? "tile"
              : "stone";
      const mat = material(
        kind === "wood" ? "#eee2d0" : "#f4f5f3",
        kind === "wood" ? 0.65 : 0.78,
        { map: texture(kind, r.width, r.height), envMapIntensity: 0.2 },
      );
      const floor = box(
        floors,
        r.width,
        0.18,
        r.height,
        r.x + r.width / 2,
        yOff - 0.09,
        r.y + r.height / 2,
        mat,
      );
      floor.userData = { room: r, floor: fi, isFloor: true, baseColor: mat.color.clone() };
      floor.castShadow = false;
      [
        ...(r.doors || []).map((o) => ({ ...o, kind: "door" })),
        ...(r.windows || []).map((o) => ({ ...o, kind: "window" })),
    ].forEach((o) => {
      const a = openingPosition(r, o);
      if (a) apertures.push({ ...a, yOff });
    });
  });
  });
  const b = bounds(),
    size = b.getSize(new THREE.Vector3()),
    center = b.getCenter(new THREE.Vector3());
  box(
    model,
    size.x + 0.8,
    0.3,
    size.z + 0.8,
    center.x,
    -0.34,
    center.z,
    material("#4f6067"),
  );
  const plaster = material(palette.plaster, 0.9, {
    map: texture("plaster"),
    clippingPlanes: cutaway ? [clip] : [],
    clipShadows: true,
    envMapIntensity: 0.18,
  });
  const exterior = plaster.clone();
  exterior.color.set(palette.exterior);
  const allWallSegments = [];
  floorPlans.forEach((plan, fi) => {
    wallSegments(plan.rooms || []).forEach((s) =>
      allWallSegments.push({ ...s, yOff: fi * STORY_HEIGHT }),
    );
  });
  allWallSegments.forEach((s) => {
    const t = s.exterior ? 0.45 : 0.3;
    // Multi-floor: exterior walls extend to the next floor level so the
    // building looks connected instead of separate floating platforms.
    const isMultiFloor = layout.floors && layout.floors > 1;
    const h = s.balcony && s.exterior
      ? 3.2
      : s.exterior && isMultiFloor
        ? STORY_HEIGHT
        : 7.2;
    const cuts = apertures
      .filter(
        (a) =>
          a.h === s.h &&
          Math.abs(a.at - s.at) < 0.08 &&
          a.a >= s.a - 0.08 &&
          a.b <= s.b + 0.08,
      )
      .sort((a, b) => a.a - b.a);
    const piece = (lo, hi, y0, y1) => {
      if (hi - lo < 0.01 || y1 - y0 < 0.01) return;
      box(
        walls,
        s.h ? hi - lo : t,
        y1 - y0,
        s.h ? t : hi - lo,
        s.h ? (lo + hi) / 2 : s.at,
        (y0 + y1) / 2 + s.yOff,
        s.h ? s.at : (lo + hi) / 2,
        s.exterior ? exterior : plaster,
      );
    };
    let start = s.a;
    cuts.forEach((a) => {
      if (a.a < start) return;
      piece(start, a.a, 0, h);
      piece(a.a, a.b, 0, Math.min(h, a.sill));
      piece(a.a, a.b, Math.min(h, a.head), h);
      start = a.b;
    });
    piece(start, s.b, 0, h);
  });
  const frameMat = material("#45575a", 0.5, {
      clippingPlanes: cutaway ? [clip] : [],
    }),
    doorMat = material("#947c63", 0.65, {
      clippingPlanes: cutaway ? [clip] : [],
    }),
    glassMat = material("#b0d2dc", 0.18, {
      transparent: true,
      opacity: 0.28,
      depthWrite: false,
      clippingPlanes: cutaway ? [clip] : [],
    });
  const seen = new Set();
  apertures.forEach((a) => {
    const key = [a.h, a.at, a.a, a.b, a.kind].join("|");
    if (seen.has(key)) return;
    seen.add(key);
    const g = new THREE.Group();
    g.position.set(
      a.h ? (a.a + a.b) / 2 : a.at,
      a.yOff || 0,
      a.h ? a.at : (a.a + a.b) / 2,
    );
    if (!a.h) g.rotation.y = Math.PI / 2;
    openings.add(g);
    const w = a.b - a.a;
    box(
      g,
      0.1,
      a.head - a.sill,
      0.38,
      -w / 2,
      (a.head + a.sill) / 2,
      0,
      frameMat,
    );
    box(
      g,
      0.1,
      a.head - a.sill,
      0.38,
      w / 2,
      (a.head + a.sill) / 2,
      0,
      frameMat,
    );
    box(g, w, 0.1, 0.38, 0, a.head, 0, frameMat);
    box(
      g,
      w - 0.14,
      a.head - a.sill - 0.14,
      0.08,
      0,
      (a.head + a.sill) / 2,
      0,
      a.kind === "door" ? doorMat : glassMat,
    );
    if (a.kind === "window") {
      box(g, w, 0.1, 0.38, 0, a.sill, 0, frameMat);
      box(
        g,
        0.06,
        a.head - a.sill,
        0.12,
        0,
        (a.head + a.sill) / 2,
        0,
        frameMat,
      );
    }
  });
  floorPlans.forEach((plan, fi) => {
    const yOff = fi * STORY_HEIGHT;
    (plan.furniture || []).forEach((f) => addAsset(f, furniture, token, yOff));
    (plan.plumbing_fixtures || []).forEach((f) =>
      addAsset(
        {
          ...f,
          x: f.x - (f.width || 1.8) / 2,
          y: f.y - (f.height || 1.8) / 2,
          width: f.width || 1.8,
          height: f.height || 1.8,
        },
        plumbing,
        token,
        yOff,
      ),
    );
    (plan.lighting || []).forEach((l, i) => {
      const y = l.type === "pendant_light" ? 5.8 : 6.9;
      const lamp = new THREE.Mesh(
        new THREE.CylinderGeometry(0.22, 0.28, 0.12, 12),
        material("#fff3d6", 0.4, { emissive: "#ffdca6", emissiveIntensity: 0.6 }),
      );
      lamp.position.set(l.x, y + yOff, l.y);
      markers.add(lamp);
      if (i < 8) {
        const p = new THREE.PointLight("#fff0d4", 35, 22, 2);
        p.position.set(l.x, 5.8 + yOff, l.y);
        illumination.add(p);
      }
    });
    (plan.plumbing_routes || []).forEach((rt) => {
      const pts = rt.path || [];
      for (let i = 1; i < pts.length; i++) {
        const a = pts[i - 1],
          b = pts[i],
          len = Math.hypot(b[0] - a[0], b[1] - a[1]);
        if (len < 0.01) continue;
        const m = box(
          plumbing,
          len,
          0.08,
          0.08,
          (a[0] + b[0]) / 2,
          0.06 + yOff,
          (a[1] + b[1]) / 2,
          material(rt.kind === "drainage" ? "#997bc0" : "#4aabc6"),
        );
        m.rotation.y = -Math.atan2(b[1] - a[1], b[0] - a[0]);
      }
    });
  });

  // Realistic 3D staircase connecting all floors, aligned with the reserved
  // staircase footprint on every floor plan.
  if (layout.staircase && layout.floors && layout.floors > 1) {
    const s = layout.staircase;
    const stairMat = material("#b9a98a", 0.5);
    const stairSideMat = material("#8d7a62", 0.55);
    const nosingMat = material("#a9a194", 0.4);
    const RISE = STORY_HEIGHT / 14;        // ~0.71 ft per riser
    const TREAD = s.height / 14;            // ~0.71 ft per tread
    const STRINGER_THICK = 0.6;             // thin stringer board thickness (ft)

    // ---- The staircase itself: thin stringers + steps for each flight ----
    const stairs = new THREE.Group();
    for (let f = 0; f < layout.floors - 1; f++) {
      const baseY = f * STORY_HEIGHT;
      // Stringers: thin vertical boards on each side following the step profile.
      // Extruded by STRINGER_THICK (0.6 ft) along the stair width, NOT the full
      // 4 ft width — that created the oversized triangular wedges.
      for (let side = 0; side < 2; side++) {
        const sideX = side === 0 ? s.x : s.x + s.width - STRINGER_THICK;
        const shape = new THREE.Shape();
        shape.moveTo(0, 0);
        for (let k = 0; k <= 14; k++) {
          shape.lineTo(k * TREAD, k * RISE);
        }
        shape.lineTo(s.height, 0);
        shape.closePath();
        const extrudeSettings = { depth: STRINGER_THICK, bevelEnabled: false };
        const geom = new THREE.ExtrudeGeometry(shape, extrudeSettings);
        const mesh = new THREE.Mesh(geom, stairSideMat);
        mesh.position.set(sideX, baseY, s.y);
        mesh.castShadow = true;
        mesh.receiveShadow = true;
        stairs.add(mesh);
      }

      // Steps: riser + tread for each step of the flight
      for (let k = 0; k < 14; k++) {
        const stepY = baseY + k * RISE;
        const stepZ = s.y + k * TREAD;
        // Riser (vertical face)
        box(
          stairs,
          s.width,
          RISE,
          0.12,
          s.x + s.width / 2,
          stepY + RISE / 2,
          stepZ + TREAD / 2 - 0.06,
          stairMat,
        );
        // Tread (horizontal walking surface)
        box(
          stairs,
          s.width,
          0.12,
          TREAD,
          s.x + s.width / 2,
          stepY + RISE,
          stepZ + TREAD / 2,
          nosingMat,
        );
      }
      // Top landing tread (level with upper floor)
      box(
        stairs,
        s.width,
        0.12,
        s.height - 14 * TREAD + TREAD,
        s.x + s.width / 2,
        baseY + STORY_HEIGHT,
        s.y + s.height - (s.height - 14 * TREAD) / 2,
        nosingMat,
      );
    }
    model.add(stairs);
  }

  walls.visible = visibility.walls;
  openings.visible = visibility.walls;
  furniture.visible = visibility.furniture;
  markers.visible = visibility.lighting;
  plumbing.visible = visibility.plumbing;
  const radius = size.length() / 2 + 4,
    sc = sun.shadow.camera;
  sc.left = sc.bottom = -radius;
  sc.right = sc.top = radius;
  sc.far = radius * 7;
  sc.updateProjectionMatrix();
  sun.target.position.copy(center);
  selectRoom(selectedId);
  resetCamera();
  updateLighting(1);
}
async function addAsset(f, target, token, yOff = 0) {
  const name = modelNames[f.type];
  if (!name || !(f.width > 0 && f.height > 0)) return;
  try {
    if (!assets.has(name))
      assets.set(
        name,
        loader.loadAsync(
          new URL(`../assets/models/${name}.glb`, import.meta.url).href,
        ),
      );
    const source = (await assets.get(name)).scene;
    if (token !== generation) return;
    const o = source.clone(true);
    o.traverse((m) => {
      if (m.isMesh) {
        m.geometry = m.geometry.clone();
        m.material = m.material.clone();
        m.material.roughness = Math.max(0.55, m.material.roughness);
        m.material.metalness = Math.min(0.15, m.material.metalness);
        m.material.envMapIntensity = 0.18;
        m.castShadow = true;
        m.receiveShadow = true;
      }
    });
    const b = new THREE.Box3().setFromObject(o),
      size = b.getSize(new THREE.Vector3());
    o.scale.set(
      f.width / (size.x || 1),
      (objectHeights[f.type] || 2) / (size.y || 1),
      f.height / (size.z || 1),
    );
    o.position.set(
      f.x - b.min.x * o.scale.x,
      -b.min.y * o.scale.y + yOff,
      f.y - b.min.z * o.scale.z,
    );
    o.userData.source = { ...f };
    target.add(o);
  } catch (e) {
    if (token === generation) {
      console.warn(`Furniture asset unavailable: ${name}`);
      const badge = document.getElementById("twinBadge");
      if (badge)
        badge.textContent =
          "Some furniture could not load · house geometry remains available";
    }
  }
}
function selectRoom(id) {
  selectedId = id;
  if (!selection) return;
  disposeTree(selection);
  selection.clear();
  let r = null, rFloor = 0;
  if (layoutRef?.floor_plans) {
    for (let fi = 0; fi < layoutRef.floor_plans.length; fi++) {
      const found = layoutRef.floor_plans[fi].rooms.find((x) => x.id === id);
      if (found) { r = found; rFloor = fi; break; }
    }
  }
  if (!r) r = layoutRef?.rooms.find((x) => x.id === id);
  const badge = document.getElementById("room3DBadge");
  if (badge) {
    badge.hidden = !r;
    badge.textContent = r
      ? `${r.label || r.type} · ${r.width.toFixed(1)} × ${r.height.toFixed(1)} ft · ${(r.area ?? r.width * r.height).toFixed(0)} sqft`
      : "";
  }
  if (!r) return;
  const y0 = rFloor * STORY_HEIGHT + 0.035;
  const points = [
    [r.x, y0, r.y],
    [r.x + r.width, y0, r.y],
    [r.x + r.width, y0, r.y + r.height],
    [r.x, y0, r.y + r.height],
    [r.x, y0, r.y],
  ].map((p) => new THREE.Vector3(...p));
  const line = new THREE.Line(
    new THREE.BufferGeometry().setFromPoints(points),
    new THREE.LineBasicMaterial({
      color: palette.selection,
      depthTest: false,
      transparent: true,
      opacity: 0.9,
    }),
  );
  line.renderOrder = 10;
  selection.add(line);
}
function fitCamera(top = false) {
  if (!layoutRef) return;
  const b = bounds(),
    center = b.getCenter(new THREE.Vector3());
  // For multi-floor, look at the middle height of the building so both
  # floors are visible in the initial view.
  center.y = layoutRef?.floors && layoutRef.floors > 1
    ? (layoutRef.floors - 1) * STORY_HEIGHT / 2
    : 1.6;
  const direction = top
    ? new THREE.Vector3(0, 1, 0.0001).normalize()
    : new THREE.Vector3(0.55, 1.3, 0.85).normalize();
  camera.position.copy(center).add(direction);
  camera.lookAt(center);
  camera.updateMatrixWorld();
  const right = new THREE.Vector3().setFromMatrixColumn(camera.matrixWorld, 0),
    up = new THREE.Vector3().setFromMatrixColumn(camera.matrixWorld, 1);
  const tan = Math.tan(THREE.MathUtils.degToRad(camera.fov) / 2);
  let distance = 0;
  for (const x of [b.min.x, b.max.x])
    for (const y of [b.min.y, b.max.y])
      for (const z of [b.min.z, b.max.z]) {
        const p = new THREE.Vector3(x, y, z).sub(center);
        const toward = p.dot(direction);
        distance = Math.max(
          distance,
          toward + Math.abs(p.dot(up)) / tan,
          toward + Math.abs(p.dot(right)) / (tan * camera.aspect),
        );
      }
  distance *= 1.16;
  camera.position.copy(center).addScaledVector(direction, distance);
  controls.target.copy(center);
  controls.minDistance = 4;
  controls.maxDistance = distance * 3;
  camera.far = Math.max(500, distance * 5);
  camera.updateProjectionMatrix();
  controls.update();
  fitted = true;
}
function resetCamera() {
  fitCamera(false);
}
function topView() {
  fitCamera(true);
}
function setCutaway(v) {
  cutaway = v;
  [walls, openings].forEach((g) =>
    g?.traverse((o) => {
      if (o.material) {
        o.material.clippingPlanes = v ? [clip] : [];
        o.material.needsUpdate = true;
      }
    }),
  );
}
function setWallsVisible(v) {
  visibility.walls = v;
  if (walls) walls.visible = v;
  if (openings) openings.visible = v;
}
function setFurnitureVisible(v) {
  visibility.furniture = v;
  if (furniture) furniture.visible = v;
}
function setLightingVisible(v) {
  visibility.lighting = v;
  if (markers) markers.visible = v;
}
function setPlumbingVisible(v) {
  visibility.plumbing = v;
  if (plumbing) plumbing.visible = v;
}
function setFloorHighlight(index) {
  if (!floors) return;
  floors.traverse((o) => {
    if (o.isMesh && o.userData && o.userData.isFloor) {
      const sel =
        index >= 0 && o.userData.room && o.userData.floor === index;
      o.material.color.set(
        sel ? new THREE.Color("#36d8cf") : o.userData.baseColor,
      );
      o.material.needsUpdate = true;
    }
  });
}
function disposeThree() {
  generation++;
  cancelAnimationFrame(frame);
  observer?.disconnect();
  window.removeEventListener("resize", resize);
  window.removeEventListener("keydown", onKey);
  window.removeEventListener("pagehide", disposeThree);
  if (renderer) {
    renderer.domElement.removeEventListener("pointerdown", onPointerDown);
    renderer.domElement.removeEventListener("pointerup", onPointerUp);
  }
  controls?.dispose();
  if (scene) disposeTree(scene);
  textures.forEach((t) => t.dispose());
  textures.clear();
  environmentTarget?.dispose();
  renderer?.dispose();
  scene = null;
  renderer = null;
  layoutRef = null;
  assets.forEach(async (promise) => {
    try {
      const gltf = await promise;
      disposeTree(gltf.scene);
    } catch {}
  });
  assets.clear();
}
window.ThreeViewer = {
  initThree,
  buildFromLayout,
  resetCamera,
  topView,
  setWallsVisible,
  setFurnitureVisible,
  setLightingVisible,
  setPlumbingVisible,
  setLightingMode,
  setCutaway,
  setFloorHighlight,
  selectRoom,
  disposeThree,
};
