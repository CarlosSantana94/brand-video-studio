// Synthwave horizon: a glowing grid floor rushing toward the camera, a striped sun and seeded mountains.
// Good as an intro, a transition or the background of a title. Colors come from brand.json.
// params: { speed: 6 (grid units per second), sun: true, mountains: true, tilt: 0.12 (camera pitch) }
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
  const p = { speed: 6, sun: true, mountains: true, tilt: 0.12, ...params };
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: transparent, preserveDrawingBuffer: true });
  renderer.setPixelRatio(1);
  renderer.setSize(width, height, false);

  const scene = new THREE.Scene();
  const sky = new THREE.Color(colors.ink_dark);
  if (!transparent) scene.background = sky;
  scene.fog = new THREE.Fog(sky, 30, 140);

  const camera = new THREE.PerspectiveCamera(60, width / height, 0.1, 400);
  camera.position.set(0, 3.2, 12);
  camera.rotation.x = -p.tilt;

  // Grid floor: one GridHelper, moved by (t * speed) mod one cell so it loops seamlessly.
  const CELL = 4, SIZE = 400;
  const grid = new THREE.GridHelper(SIZE, SIZE / CELL, colors.accent, colors.accent);
  grid.material.transparent = true;
  grid.material.opacity = 0.9;
  scene.add(grid);
  const floor = new THREE.Mesh(new THREE.PlaneGeometry(SIZE, SIZE), new THREE.MeshBasicMaterial({ color: colors.bg }));
  floor.rotation.x = -Math.PI / 2;
  floor.position.y = -0.02;
  scene.add(floor);

  // Sun: a disc with a vertical gradient and horizontal cut bands, drawn once into a canvas texture.
  if (p.sun) {
    const c = document.createElement("canvas");
    c.width = c.height = 512;
    const g = c.getContext("2d");
    const grad = g.createLinearGradient(0, 0, 0, 512);
    grad.addColorStop(0, colors.highlight);
    grad.addColorStop(1, colors.accent);
    g.fillStyle = grad;
    g.beginPath(); g.arc(256, 256, 250, 0, Math.PI * 2); g.fill();
    g.globalCompositeOperation = "destination-out";
    for (let k = 0; k < 7; k++) g.fillRect(0, 300 + k * 30, 512, 4 + k * 2.2);
    const tex = new THREE.CanvasTexture(c);
    tex.colorSpace = THREE.SRGBColorSpace;
    const sun = new THREE.Mesh(new THREE.PlaneGeometry(60, 60), new THREE.MeshBasicMaterial({ map: tex, transparent: true, fog: false }));
    sun.position.set(0, 18, -150);
    scene.add(sun);
  }

  // Mountains: two seeded ridges of triangles on the horizon.
  if (p.mountains) {
    const rnd = mulberry32(7);
    for (const [z, shade] of [[-120, 0.55], [-100, 0.85]]) {
      const pts = [];
      for (let x = -160; x <= 160; x += 8) pts.push(new THREE.Vector2(x, 2 + rnd() * 16 * shade));
      const shape = new THREE.Shape([new THREE.Vector2(-160, 0), ...pts, new THREE.Vector2(160, 0)]);
      const col = new THREE.Color(colors.ink).lerp(new THREE.Color(colors.ink_dark), 1 - shade);
      const m = new THREE.Mesh(new THREE.ShapeGeometry(shape), new THREE.MeshBasicMaterial({ color: col, fog: false }));
      m.position.set(0, 0, z);
      scene.add(m);
      const edge = new THREE.LineSegments(new THREE.EdgesGeometry(m.geometry), new THREE.LineBasicMaterial({ color: colors.accent, fog: false }));
      edge.position.copy(m.position);
      scene.add(edge);
    }
  }

  return (t) => {
    grid.position.z = (t * p.speed) % CELL;
    camera.position.y = 3.2 + Math.sin(t * 0.8) * 0.25;
    renderer.render(scene, camera);
  };
}
