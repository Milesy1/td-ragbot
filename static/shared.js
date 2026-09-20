// shared.js - theme handling + hero animation (Three.js port of the
// rotating cylinder-line scene from mileswaite.net's homepage hero).
// Used by both index.html (chat) and about.html.
const THEME_KEY = "td-ragbot-theme";

function applyTheme(theme) {
  const root = document.documentElement;
  const hljsDark = document.getElementById("hljs-dark-theme");
  const hljsLight = document.getElementById("hljs-light-theme");
  const themeToggle = document.getElementById("theme-toggle");
  if (theme === "light") {
    root.setAttribute("data-theme", "light");
    if (hljsDark) hljsDark.disabled = true;
    if (hljsLight) hljsLight.disabled = false;
    if (themeToggle) themeToggle.setAttribute("aria-pressed", "true");
  } else {
    root.removeAttribute("data-theme");
    if (hljsDark) hljsDark.disabled = false;
    if (hljsLight) hljsLight.disabled = true;
    if (themeToggle) themeToggle.setAttribute("aria-pressed", "false");
  }
}

function initTheme() {
  let savedTheme = "dark";
  try {
    savedTheme = localStorage.getItem(THEME_KEY) || "dark";
  } catch (e) { /* localStorage unavailable - default to dark */ }
  applyTheme(savedTheme);

  const themeToggle = document.getElementById("theme-toggle");
  if (themeToggle) {
    themeToggle.addEventListener("click", () => {
      const current = document.documentElement.getAttribute("data-theme") === "light" ? "light" : "dark";
      const next = current === "light" ? "dark" : "light";
      applyTheme(next);
      try { localStorage.setItem(THEME_KEY, next); } catch (e) { /* ignore */ }
    });
  }
}

let heroAnimationId = null;
let heroRenderer = null;
let headerSnapshotTaken = false;

function captureHeaderSnapshot(renderer) {
  if (headerSnapshotTaken) return;
  try {
    const dataUrl = renderer.domElement.toDataURL("image/png");
    const logoEl = document.getElementById("header-logo");
    const imgEl = document.getElementById("header-logo-img");
    if (imgEl) imgEl.src = dataUrl;
    if (logoEl) logoEl.classList.add("has-snapshot");
    const favicon = document.getElementById("favicon");
    if (favicon) favicon.href = dataUrl;
    headerSnapshotTaken = true;
  } catch (e) {
    // Canvas capture can fail in rare cases (e.g. context lost) - the
    // SVG fallback stays visible, which is fine.
  }
}

function initHeroAnimation(containerId) {
  const container = document.getElementById(containerId || "hero-canvas");
  if (!container || typeof THREE === "undefined") return;

  const size = container.clientWidth || 260;
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(75, 1, 0.1, 100);
  camera.position.set(0, 0, 3.5);
  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false, preserveDrawingBuffer: true });
  renderer.setSize(size, size);
  container.innerHTML = "";
  container.appendChild(renderer.domElement);
  heroRenderer = renderer;

  scene.add(new THREE.AmbientLight(0xffffff, 1));
  const dir = new THREE.DirectionalLight(0xffffff, 1);
  dir.position.set(5, 5, 5);
  scene.add(dir);
  const point = new THREE.PointLight(0xff00ff, 0.5);
  point.position.set(-5, 0, 3);
  scene.add(point);

  const container3d = new THREE.Group();
  container3d.rotation.x = 0.5;
  container3d.rotation.z = 0.2;
  scene.add(container3d);

  function randomSeed(row, col, offset) {
    const seed = row * 100 + col + (offset || 0);
    return (Math.sin(seed) * 10000) % 1;
  }

  const columns = 7, rows = 5;
  const radii = [1.2, 1, 0.8];
  const colors = [0xffffff, 0xff0000, 0x00ff00];
  const offsets = [2000, 0, 1000];
  const reverses = [false, false, true];
  const squareHeight = 0.55, heightSpacing = 0.65;
  const anglePerSquare = (Math.PI * 2) / columns;
  const linesPerSquare = 7;
  const groups = [];

  for (let r = 0; r < radii.length; r++) {
    for (let row = 0; row < rows; row++) {
      const yPos = (row - (rows - 1) / 2) * heightSpacing;
      for (let col = 0; col < columns; col++) {
        if (randomSeed(row, col, offsets[r]) < 0.4) continue;
        const startAngle = (col / columns) * Math.PI * 2 - anglePerSquare / 2;
        const endAngle = startAngle + anglePerSquare * 0.9;
        const isFast = (col % 2 === 1);
        const speed = isFast ? 0.05625 : 0.0225;

        for (let line = 0; line < linesPerSquare; line++) {
          const lineYOffset = (line - (linesPerSquare - 1) / 2) * (squareHeight / linesPerSquare);
          const lineY = yPos + lineYOffset;
          const points = [];
          const segments = 20;
          for (let i = 0; i <= segments; i++) {
            const angle = startAngle + (endAngle - startAngle) * (i / segments);
            points.push(new THREE.Vector3(Math.cos(angle) * radii[r], lineY, Math.sin(angle) * radii[r]));
          }
          const geometry = new THREE.BufferGeometry().setFromPoints(points);
          const material = new THREE.LineBasicMaterial({ color: colors[r] });
          const line3d = new THREE.Line(geometry, material);
          const group = new THREE.Group();
          group.add(line3d);
          container3d.add(group);
          groups.push({ group, speed, reverse: reverses[r] });
        }
      }
    }
  }

  let frameCount = 0;
  function animate() {
    heroAnimationId = requestAnimationFrame(animate);
    groups.forEach(g => { g.group.rotation.y += g.reverse ? -g.speed : g.speed; });
    renderer.render(scene, camera);
    frameCount++;
    if (frameCount === 45) captureHeaderSnapshot(renderer);
  }
  animate();
}

function stopHeroAnimation() {
  if (heroAnimationId !== null) {
    cancelAnimationFrame(heroAnimationId);
    heroAnimationId = null;
  }
  if (heroRenderer) {
    heroRenderer.dispose();
    heroRenderer = null;
  }
}
