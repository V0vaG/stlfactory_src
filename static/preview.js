/**
 * STL preview only. Three.js is loaded on demand when Preview is clicked so CDN failures
 * do not block the parameter text boxes (handled by params-ui.js).
 */

const form = document.querySelector("form[action='/download-model-stl']");
const previewBtn = document.getElementById("previewBtn");
const modal = document.getElementById("previewModal");
const canvas = document.getElementById("previewCanvas");
const errorBox = document.getElementById("previewError");

let renderer;
let scene;
let camera;
let controls;
let mesh;
let animationFrameId;
let THREE;
let OrbitControlsCtor;
let STLLoaderCtor;

async function loadThree() {
  if (THREE) return;
  THREE = await import("https://unpkg.com/three@0.164.1/build/three.module.js");
  const oc = await import(
    "https://unpkg.com/three@0.164.1/examples/jsm/controls/OrbitControls.js"
  );
  const sl = await import(
    "https://unpkg.com/three@0.164.1/examples/jsm/loaders/STLLoader.js"
  );
  OrbitControlsCtor = oc.OrbitControls;
  STLLoaderCtor = sl.STLLoader;
}

function ensureViewer() {
  if (renderer) return;
  renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));

  scene = new THREE.Scene();
  scene.background = new THREE.Color(0xf1f5f9);

  camera = new THREE.PerspectiveCamera(45, 1, 0.1, 100000);
  camera.position.set(140, 120, 160);

  const hemi = new THREE.HemisphereLight(0xffffff, 0x64748b, 1.0);
  scene.add(hemi);
  const dir = new THREE.DirectionalLight(0xffffff, 1.0);
  dir.position.set(150, 200, 100);
  scene.add(dir);

  controls = new OrbitControlsCtor(camera, canvas);
  controls.enableDamping = true;
}

function resizeViewer() {
  if (!renderer || !camera) return;
  const width = canvas.clientWidth;
  const height = canvas.clientHeight;
  if (width === 0 || height === 0) return;
  renderer.setSize(width, height, false);
  camera.aspect = width / height;
  camera.updateProjectionMatrix();
}

function animate() {
  controls?.update();
  renderer?.render(scene, camera);
  animationFrameId = requestAnimationFrame(animate);
}

function setError(message) {
  if (!message) {
    errorBox.hidden = true;
    errorBox.textContent = "";
    return;
  }
  errorBox.hidden = false;
  errorBox.textContent = message;
}

function clearMesh() {
  if (!mesh || !scene) return;
  scene.remove(mesh);
  mesh.geometry.dispose();
  mesh.material.dispose();
  mesh = null;
}

async function loadPreviewStl() {
  setError("");
  const formData = new FormData(form);
  const response = await fetch("/preview-model-stl", {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    let message = "Preview failed.";
    try {
      const payload = await response.json();
      message = payload.error || message;
    } catch {
      // keep default
    }
    throw new Error(message);
  }

  const blob = await response.blob();
  const arrayBuffer = await blob.arrayBuffer();
  const geometry = new STLLoaderCtor().parse(arrayBuffer);
  geometry.computeVertexNormals();
  geometry.computeBoundingBox();

  const material = new THREE.MeshStandardMaterial({
    color: 0x2563eb,
    metalness: 0.15,
    roughness: 0.45,
  });
  const newMesh = new THREE.Mesh(geometry, material);
  clearMesh();
  mesh = newMesh;
  scene.add(mesh);

  const box = geometry.boundingBox;
  const center = new THREE.Vector3();
  box.getCenter(center);
  mesh.position.sub(center);

  const size = new THREE.Vector3();
  box.getSize(size);
  const maxDim = Math.max(size.x, size.y, size.z, 1);

  camera.position.set(maxDim * 1.6, maxDim * 1.2, maxDim * 1.6);
  camera.near = maxDim / 1000;
  camera.far = maxDim * 100;
  camera.updateProjectionMatrix();
  controls.target.set(0, 0, 0);
  controls.update();
}

async function openModal() {
  modal.hidden = false;
  await loadThree();
  ensureViewer();
  resizeViewer();
  if (!animationFrameId) animate();
}

function closeModal() {
  modal.hidden = true;
  setError("");
  if (animationFrameId) {
    cancelAnimationFrame(animationFrameId);
    animationFrameId = null;
  }
}

previewBtn?.addEventListener("click", async () => {
  try {
    await openModal();
    await loadPreviewStl();
  } catch (error) {
    setError(error instanceof Error ? error.message : "Preview failed.");
  }
});

modal?.addEventListener("click", (event) => {
  const target = event.target;
  if (!(target instanceof Element)) return;
  if (target.hasAttribute("data-close-preview")) {
    closeModal();
  }
});

window.addEventListener("resize", () => {
  resizeViewer();
});
