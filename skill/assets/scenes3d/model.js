// A hero 3D model (glTF / GLB): a slow turn and a camera dive toward it, lit with a warm key and a cool rim.
// Without params.src it shows a placeholder knot, so the timing can be checked before the model exists.
// params: { src: "assets/models/car.glb", turn: 0.6 (radians per second), dive: 0.45 (how far the camera
//           closes in, 0-0.9), height: 0.15, spin: true, background: true }
// Contract (see references/3d-scenes.md): export an async setup that returns render(t), pure in t.

import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";

const ease = (x) => 1 - Math.pow(1 - Math.min(Math.max(x, 0), 1), 3);

export default async function setup({ THREE, canvas, width, height, duration, colors, params, transparent }) {
  const p = { turn: 0.6, dive: 0.45, height: 0.15, spin: true, background: true, ...params };
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: transparent, preserveDrawingBuffer: true });
  renderer.setPixelRatio(1);
  renderer.setSize(width, height, false);
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  if (transparent) renderer.setClearColor(0x000000, 0);

  const scene = new THREE.Scene();
  if (!transparent && p.background) scene.background = new THREE.Color(colors.ink_dark);

  // Physically based lights (always on since r165): a warm key, a cool rim in the accent and a soft fill.
  scene.add(new THREE.HemisphereLight(colors.light, colors.ink_dark, 0.6));
  const key = new THREE.DirectionalLight(0xfff1e0, 3);
  key.position.set(4, 6, 5);
  scene.add(key);
  const rim = new THREE.DirectionalLight(colors.accent, 4);
  rim.position.set(-5, 3, -6);
  scene.add(rim);

  let model;
  if (p.src) {
    const gltf = await new GLTFLoader().loadAsync(p.src);
    model = gltf.scene;
  } else {
    model = new THREE.Mesh(new THREE.TorusKnotGeometry(1, 0.35, 220, 32),
      new THREE.MeshStandardMaterial({ color: colors.highlight, roughness: 0.45, metalness: 0.3 }));
  }
  // Fit the model to a 3-unit box, resting on the floor at the origin.
  const box = new THREE.Box3().setFromObject(model);
  const size = box.getSize(new THREE.Vector3()), center = box.getCenter(new THREE.Vector3());
  const s = 3 / Math.max(size.x, size.y, size.z);
  model.scale.setScalar(s);
  model.position.sub(center.multiplyScalar(s));
  model.position.y += (size.y * s) / 2;
  const pivot = new THREE.Group();
  pivot.add(model);
  scene.add(pivot);

  // Contact shadow: a soft dark disc under the model, cheaper and steadier than a shadow map.
  const sh = document.createElement("canvas");
  sh.width = sh.height = 128;
  const g = sh.getContext("2d");
  const grad = g.createRadialGradient(64, 64, 0, 64, 64, 64);
  grad.addColorStop(0, "rgba(0,0,0,0.55)");
  grad.addColorStop(1, "rgba(0,0,0,0)");
  g.fillStyle = grad; g.fillRect(0, 0, 128, 128);
  const shadow = new THREE.Mesh(new THREE.PlaneGeometry(5, 5), new THREE.MeshBasicMaterial({ map: new THREE.CanvasTexture(sh), transparent: true, depthWrite: false }));
  shadow.rotation.x = -Math.PI / 2;
  shadow.position.y = 0.01;
  scene.add(shadow);

  const camera = new THREE.PerspectiveCamera(35, width / height, 0.1, 100);
  const far = width < height ? 13 : 9;
  const target = new THREE.Vector3(0, 1.5, 0);

  return (t) => {
    const k = ease(t / Math.max(duration, 0.001));
    const dist = far * (1 - p.dive * k);
    const ang = 0.5 - 0.35 * k;
    camera.position.set(Math.sin(ang) * dist, 1.5 + dist * p.height + 1.2 * (1 - k), Math.cos(ang) * dist);
    camera.lookAt(target);
    if (p.spin) pivot.rotation.y = t * p.turn;
    renderer.render(scene, camera);
  };
}
