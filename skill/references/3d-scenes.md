# 3D scenes with three.js

Add a three.js scene to any video through `scenes` in `spec.json`. Use it for an intro, a transition, a
backdrop behind a title, particles over footage, or a product or object as the payoff. 3D costs render time
and attention, so use it where it carries the story, not as decoration on every video.

For the three.js API itself, load the **threejs-skills** (`threejs-fundamentals`, `threejs-lighting`,
`threejs-materials`, `threejs-loaders` and the others). They target three.js r186, the version `build.py`
loads, and list the outdated patterns to avoid. Install them once:

```bash
npx skills add cloudai-x/threejs-skills
```

## In spec.json

```json
"scenes": [
  { "t": 0, "d": 2.6, "src": "neon-grid" },
  { "t": 4, "d": 4, "src": "particles", "mode": "overlay", "params": { "count": 1500 } },
  { "t": 10, "d": 3, "src": "model", "params": { "src": "assets/models/car.glb" } },
  { "t": 14, "d": 2, "src": "scenes/my-scene.js", "sfx": false }
]
```

- **`t`, `d`:** start and length in seconds of the assembled video.
- **`src`:** a ready-made scene, or a `.js` file of your own relative to the video folder.
- **`mode`:** `full` (default) draws an opaque scene that covers the footage. `overlay` draws on a
  transparent background over the footage.
- **`params`:** passed to the scene.
- **`sfx`:** the effect played when it starts, `whoosh` by default. `false` for none.

Scenes sit above the footage and under the hook, layers and captions, so a hook can play over a 3D intro.
The audio of the clip keeps playing under a `full` scene. For a 3D intro with no clip audio under it,
start the clip's `ranges` later or mute the start.

## Ready-made scenes

All of them take their colors from `brand.json` (`accent`, `highlight`, `ink`, `ink_dark`, `bg`).

| `src` | What it is | `params` |
|---|---|---|
| `neon-grid` | Synthwave horizon: grid floor rushing forward, striped sun, mountain ridges | `speed`, `sun`, `mountains`, `tilt` |
| `particles` | Glowing particles flying toward the camera. Works as `overlay` | `count`, `speed`, `size`, `depth`, `spin` |
| `model` | A glTF/GLB model that turns while the camera dives toward it. Warm key light, cool rim light, contact shadow | `src`, `turn`, `dive`, `height`, `spin`, `background` |

`model` without `params.src` shows a placeholder knot, so the timing can be checked before the model exists.
Put models in `<video>/assets/models/` and only use models you have the rights to. Compress big ones with
gltf-transform (`threejs-asset-pipeline`).

## Writing your own scene

A scene is an ES module whose default export sets everything up once and returns `render(t)`:

```js
export default async function setup({ THREE, canvas, width, height, duration, colors, params, transparent }) {
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: transparent, preserveDrawingBuffer: true });
  renderer.setPixelRatio(1);
  renderer.setSize(width, height, false);
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(50, width / height, 0.1, 100);
  // ... build meshes, load models with await, simulate anything heavy into arrays here ...
  return (t) => {
    // set every moving thing from t alone, then:
    renderer.render(scene, camera);
  };
}
```

Addons import from `three/addons/...`, for example
`import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js"`. `build.py` writes the import map.

The rules that make it render correctly:

- **`render(t)` is a pure function of `t`.** HyperFrames seeks frames out of order and in parallel. Never
  use `requestAnimationFrame`, `setAnimationLoop`, `Timer`/`Clock`, `getDelta()`, or anything that
  accumulates from the previous frame. Compute positions from start values plus `t`, as `particles.js` does.
- **Seed every random choice** with a small PRNG such as `mulberry32`, never `Math.random()`.
- **Do heavy work in `setup`:** loading models, compiling shaders, physics. Bake a simulation into arrays
  and look up the state at `t`.
- **Keep `setPixelRatio(1)`** and the given `width`/`height`. The video already renders at full size.
- **Clamp anything that can divide by zero.** One NaN pixel under bloom turns the frame black.
- **No text in 3D for hooks or captions.** Keep words in the hook and layers, where they stay sharp and
  readable.

## Look

- One hero object beats a crowd. Dive into it or fly past it rather than orbiting it forever.
- Light: warm key, cool rim in the accent color, dark background. Roughness about 0.45 or more on glossy
  materials, so highlights do not turn into white streaks.
- In 9:16, the middle third of the frame is what survives the profile grid crop, so center the hero there.

## Check

```bash
npx --yes hyperframes check --json
npx --yes hyperframes snapshot --at <start+0.2>,<middle>,<end-0.2>
```

Snapshot the start, middle and end of each scene. A blank or black canvas usually means `setup` threw: look
at the runtime findings in the check report. If a frame takes too long to draw, lower `count`, polygons or
texture sizes (`threejs-performance`).
