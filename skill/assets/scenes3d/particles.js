// A field of glowing particles flying toward the camera, in the brand's accent and highlight colors.
// Use mode "overlay" to put it over footage (transparent background), or "full" as a backdrop.
// params: { count: 2500, speed: 18, size: 0.35, depth: 120, spin: 0.15 }
// Contract (see references/3d-scenes.md): export an async setup that returns render(t), pure in t.

function mulberry32(seed) {
  return () => {
    seed |= 0; seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export default async function setup({ THREE, canvas, width, height, colors, params, transparent }) {
  const p = { count: 2500, speed: 18, size: 0.35, depth: 120, spin: 0.15, ...params };
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: transparent, preserveDrawingBuffer: true });
  renderer.setPixelRatio(1);
  renderer.setSize(width, height, false);
  if (transparent) renderer.setClearColor(0x000000, 0);

  const scene = new THREE.Scene();
  if (!transparent) scene.background = new THREE.Color(colors.ink_dark);
  const camera = new THREE.PerspectiveCamera(70, width / height, 0.1, p.depth + 10);

  // Start positions are seeded; the position at t is computed from them, never accumulated.
  const rnd = mulberry32(42);
  const base = new Float32Array(p.count * 3);
  const pos = new Float32Array(p.count * 3);
  const col = new Float32Array(p.count * 3);
  const a = new THREE.Color(colors.accent), b = new THREE.Color(colors.highlight), c = new THREE.Color();
  for (let i = 0; i < p.count; i++) {
    const r = 2 + rnd() * 30, ang = rnd() * Math.PI * 2;
    base.set([Math.cos(ang) * r, Math.sin(ang) * r, -rnd() * p.depth], i * 3);
    c.copy(a).lerp(b, rnd());
    col.set([c.r, c.g, c.b], i * 3);
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute("position", new THREE.BufferAttribute(pos, 3));
  geo.setAttribute("color", new THREE.BufferAttribute(col, 3));

  // A soft round sprite drawn once, so points glow instead of rendering as squares.
  const dot = document.createElement("canvas");
  dot.width = dot.height = 64;
  const g = dot.getContext("2d");
  const grad = g.createRadialGradient(32, 32, 0, 32, 32, 32);
  grad.addColorStop(0, "rgba(255,255,255,1)");
  grad.addColorStop(0.4, "rgba(255,255,255,0.6)");
  grad.addColorStop(1, "rgba(255,255,255,0)");
  g.fillStyle = grad; g.fillRect(0, 0, 64, 64);
  const mat = new THREE.PointsMaterial({ size: p.size, map: new THREE.CanvasTexture(dot), vertexColors: true,
    transparent: true, depthWrite: false, blending: THREE.AdditiveBlending });
  const points = new THREE.Points(geo, mat);
  scene.add(points);

  return (t) => {
    for (let i = 0; i < p.count; i++) {
      const z = base[i * 3 + 2] + t * p.speed;
      pos[i * 3] = base[i * 3];
      pos[i * 3 + 1] = base[i * 3 + 1];
      pos[i * 3 + 2] = -(((-z) % p.depth + p.depth) % p.depth);   // wrap back to the far end
    }
    geo.attributes.position.needsUpdate = true;
    points.rotation.z = t * p.spin;
    renderer.render(scene, camera);
  };
}
