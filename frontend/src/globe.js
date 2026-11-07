import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { feature, mesh } from 'topojson-client';
import { geoEquirectangular, geoPath, geoGraticule10 } from 'd3-geo';
import atlas from 'world-atlas/countries-110m.json';
import { coordinates, importance } from './model.js';

const RADIUS = 1.35;
const toVector = (lat, lon, radius = RADIUS + 0.015) => {
  const a = THREE.MathUtils.degToRad(lat), b = THREE.MathUtils.degToRad(lon);
  return new THREE.Vector3(radius * Math.cos(a) * Math.cos(b), radius * Math.sin(a), -radius * Math.cos(a) * Math.sin(b));
};
function earthTexture() {
  const canvas = document.createElement('canvas');
  canvas.width = 2048; canvas.height = 1024;
  const context = canvas.getContext('2d');
  const projection = geoEquirectangular().translate([1024, 512]).scale(1024 / Math.PI);
  const path = geoPath(projection, context);
  context.fillStyle = '#102028'; context.fillRect(0, 0, 2048, 1024);
  context.beginPath(); path(feature(atlas, atlas.objects.countries));
  context.fillStyle = '#30464a'; context.fill();
  context.beginPath(); path(mesh(atlas, atlas.objects.countries));
  context.strokeStyle = '#536767'; context.lineWidth = 0.85; context.stroke();
  context.beginPath(); path(geoGraticule10());
  context.strokeStyle = '#50747640'; context.lineWidth = 0.65; context.stroke();
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.anisotropy = 8;
  return texture;
}
function makeStars() {
  const vertices = [];
  let seed = 27637;
  const random = () => ((seed = (seed * 16807) % 2147483647) - 1) / 2147483646;
  for (let i = 0; i < 600; i++) {
    const p = new THREE.Vector3(random() * 2 - 1, random() * 2 - 1, random() * 2 - 1).normalize().multiplyScalar(25 + random() * 20);
    vertices.push(p.x, p.y, p.z);
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.Float32BufferAttribute(vertices, 3));
  return new THREE.Points(geometry, new THREE.PointsMaterial({ color: '#abc9ca', size: 0.022, transparent: true, opacity: 0.6, depthWrite: false }));
}

export class FrontierGlobe {
  constructor(container, { onSelect, onCluster, onRotate, onFallback }) {
    this.container = container;
    this.onSelect = onSelect;
    this.onCluster = onCluster;
    this.onRotate = onRotate;
    this.onFallback = onFallback;
    this.records = [];
    this.selected = null;
    this.initialFocusApplied = false;
    this.userInteracted = false;
    this.width = 1; this.height = 1;
    this.reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
    this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: 'low-power' });
    this.renderer.setPixelRatio(Math.min(devicePixelRatio || 1, 1.75));
    this.renderer.setClearColor(0x000000, 0);
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    this.renderer.domElement.setAttribute('aria-hidden', 'true');
    this.renderer.domElement.addEventListener('webglcontextlost', (event) => { event.preventDefault(); this.stop(); this.onFallback?.('3D 渲染暂不可用，事件列表仍可正常阅读。'); });
    container.append(this.renderer.domElement);
    this.labels = document.createElement('div'); this.labels.className = 'globe-labels';
    container.append(this.labels);
    this.scene = new THREE.Scene();
    this.camera = new THREE.PerspectiveCamera(38, 1, 0.1, 100);
    this.camera.position.copy(toVector(24, 80, 4.8));
    this.camera.lookAt(0, 0, 0);
    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.controls.enablePan = false;
    this.controls.enableDamping = !this.reduced;
    this.controls.dampingFactor = 0.06;
    this.controls.minDistance = 2.5; this.controls.maxDistance = 7.2;
    this.controls.rotateSpeed = 0.55; this.controls.zoomSpeed = 0.65;
    this.controls.autoRotate = !this.reduced; this.controls.autoRotateSpeed = 0.22;
    this.controls.minPolarAngle = 0.13; this.controls.maxPolarAngle = Math.PI - 0.13;
    this.controls.addEventListener('start', () => { this.userInteracted = true; this.focusAnimation = null; this.setAutoRotate(false); });
    this.earth = new THREE.Mesh(new THREE.SphereGeometry(RADIUS, 96, 64), new THREE.MeshPhongMaterial({ map: earthTexture(), shininess: 8, specular: new THREE.Color('#13292b') }));
    this.scene.add(this.earth);
    this.scene.add(new THREE.AmbientLight('#9bb7c5', 2.05));
    const key = new THREE.DirectionalLight('#c0e7de', 2.2); key.position.set(-3, 5, 3); this.scene.add(key);
    const fill = new THREE.DirectionalLight('#387580', 1.1); fill.position.set(3, -2, -4); this.scene.add(fill);
    const atmosphere = new THREE.Mesh(new THREE.SphereGeometry(RADIUS * 1.025, 64, 48), new THREE.ShaderMaterial({
      uniforms: { glowColor: { value: new THREE.Color('#5bcdb9') } },
      vertexShader: 'varying vec3 vNormal; varying vec3 vPosition; void main(){ vNormal = normalize(normalMatrix * normal); vec4 p = modelViewMatrix * vec4(position, 1.0); vPosition = p.xyz; gl_Position = projectionMatrix * p; }',
      fragmentShader: 'uniform vec3 glowColor; varying vec3 vNormal; varying vec3 vPosition; void main(){ float rim = pow(1.0 - abs(dot(normalize(vNormal), normalize(-vPosition))), 4.0); gl_FragColor = vec4(glowColor, rim * 0.28); }',
      transparent: true, depthWrite: false, side: THREE.FrontSide, blending: THREE.AdditiveBlending
    }));
    this.scene.add(atmosphere);
    this.scene.add(makeStars());
    this.resizeObserver = new ResizeObserver(() => this.resize());
    this.resizeObserver.observe(container);
    this.visibilityHandler = () => { if (!document.hidden) { this.lastFrame = 0; this.lastCluster = 0; } };
    document.addEventListener('visibilitychange', this.visibilityHandler);
    this.animate = this.animate.bind(this);
    this.resize(); this.raf = requestAnimationFrame(this.animate);
  }

  resize() {
    this.width = Math.max(1, this.container.clientWidth);
    this.height = Math.max(1, this.container.clientHeight);
    this.camera.aspect = this.width / this.height;
    this.camera.updateProjectionMatrix();
    this.renderer.setSize(this.width, this.height, false);
    this.lastCluster = 0;
  }

  setEvents(events, newIds = new Set()) {
    this.records = events.flatMap((event) => coordinates(event).map((location) => ({ event, location, vector: toVector(location.latitude, location.longitude), isNew: newIds.has(event.id) })));
    // Orient once when the first real location arrives; later refreshes never reclaim the view.
    if (!this.initialFocusApplied && this.records.length) {
      this.initialFocusApplied = true;
      if (!this.userInteracted && !this.selected) {
        const first = [...this.records].sort((a, b) => importance(b.event) - importance(a.event))[0];
        const target = toVector(first.location.latitude, first.location.longitude, this.camera.position.length());
        if (this.reduced) { this.camera.position.copy(target); this.controls.update(); }
        else this.focusAnimation = { start: performance.now(), from: this.camera.position.clone(), to: target };
      }
    }
    this.lastCluster = 0;
    this.updateClusters();
  }

  setSelected(id) { this.selected = id; this.lastCluster = 0; }

  focus(event) {
    const location = coordinates(event)[0];
    if (!location) return false;
    this.setAutoRotate(false); this.selected = event.id;
    const target = toVector(location.latitude, location.longitude, 3.6);
    if (this.reduced) { this.camera.position.copy(target); this.controls.update(); }
    else this.focusAnimation = { start: performance.now(), from: this.camera.position.clone(), to: target };
    this.lastCluster = 0;
    return true;
  }

  setAutoRotate(enabled, userInitiated = false) { if (userInitiated) { this.userInteracted = true; this.focusAnimation = null; } this.controls.autoRotate = Boolean(enabled); this.onRotate?.(this.controls.autoRotate); }
  zoom(direction) { this.userInteracted = true; this.focusAnimation = null; this.camera.position.multiplyScalar(direction > 0 ? 0.88 : 1.13).clampLength(2.5, 7.2); this.controls.update(); this.lastCluster = 0; }
  reset() { this.userInteracted = true; this.focusAnimation = null; this.camera.position.copy(toVector(24, 80, 4.8)); this.controls.target.set(0, 0, 0); this.controls.update(); this.selected = null; this.lastCluster = 0; }

  project(record) {
    const cameraDistance = this.camera.position.length();
    // Hide pins on the far hemisphere and near the silhouette; no through-earth labels.
    if (record.vector.dot(this.camera.position) / (record.vector.length() * cameraDistance) < RADIUS / cameraDistance + 0.02) return null;
    const p = record.vector.clone().project(this.camera);
    const x = (p.x * 0.5 + 0.5) * this.width, y = (-p.y * 0.5 + 0.5) * this.height;
    if (p.z > 1 || x < 12 || y < 12 || x > this.width - 12 || y > this.height - 12) return null;
    return { x, y };
  }

  updateClusters() {
    if (!this.labels) return;
    const groups = [];
    const records = [...this.records].sort((a, b) => Number(b.event.id === this.selected) - Number(a.event.id === this.selected) || importance(b.event) - importance(a.event));
    for (const record of records) {
      const p = this.project(record);
      if (!p) continue;
      const group = groups.find((g) => Math.hypot(g.p.x - p.x, g.p.y - p.y) < 40);
      if (group) { if (!group.records.some((r) => r.event.id === record.event.id)) group.records.push(record); }
      else groups.push({ records: [record], p, record });
    }
    // One compact news card on mobile, up to two on desktop; keep them clear of the HUD and each other.
    const compact = this.width < 620;
    const cardWidth = compact ? 156 : 190, cardHeight = compact ? 61 : 66;
    const stageRect = this.container.getBoundingClientRect(), panelRect = this.container.parentElement.getBoundingClientRect();
    const leftEdge = Math.max(12, panelRect.left - stageRect.left + 18);
    const rightEdge = Math.min(this.width - 12, panelRect.right - stageRect.left - 18);
    const topEdge = Math.max(72, panelRect.top - stageRect.top + 82);
    const bottomEdge = Math.min(this.height - 92, panelRect.bottom - stageRect.top - 118);
    const previews = new Map(), previewRects = [];
    for (const group of groups) {
      if (previews.size >= (compact ? 1 : 2)) break;
      if (!group.record.event.title || rightEdge - leftEdge < cardWidth || bottomEdge - topEdge < cardHeight) continue;
      let left = group.p.x + 20;
      if (left + cardWidth > rightEdge) left = group.p.x - cardWidth - 20;
      left = Math.max(leftEdge, Math.min(rightEdge - cardWidth, left));
      const top = Math.max(topEdge, Math.min(bottomEdge - cardHeight, group.p.y - cardHeight / 2));
      if (Math.abs(top + cardHeight / 2 - group.p.y) > 74) continue;
      const rect = { left, top, right: left + cardWidth, bottom: top + cardHeight };
      if (previewRects.some((r) => rect.left < r.right + 12 && rect.right + 12 > r.left && rect.top < r.bottom + 12 && rect.bottom + 12 > r.top)) continue;
      previews.set(group, { left: left - group.p.x + 16, top: top - group.p.y + 16 }); previewRects.push(rect);
    }
    // Stable DOM identities preserve keyboard focus while the globe moves or refreshes.
    const existing = new Map([...this.labels.children].map((el) => [el.dataset.key, el]));
    groups.slice(0, 65).forEach((group, index) => {
      const key = `${group.record.event.id}:${group.record.location.latitude}:${group.record.location.longitude}`;
      let button = existing.get(key);
      existing.delete(key);
      if (!button) {
        button = document.createElement('button'); button.type = 'button'; button.className = 'map-pin'; button.dataset.key = key;
        const dot = document.createElement('span'); dot.className = 'pin-dot';
        const label = document.createElement('span'); label.className = 'pin-label';
        const place = document.createElement('span'); place.className = 'pin-place';
        const headline = document.createElement('span'); headline.className = 'pin-headline';
        label.append(place, headline);
        button.append(dot, label);
        button.addEventListener('click', () => {
          const records = button._group.records;
          if (records.length > 1) this.onCluster?.(records.map((r) => r.event), records[0].location.name);
          else this.onSelect?.(records[0].event.id);
        });
        button.addEventListener('focus', () => this.setAutoRotate(false));
        this.labels.append(button);
      }
      button._group = group;
      const count = group.records.length;
      button.classList.toggle('is-cluster', count > 1);
      button.classList.toggle('is-selected', group.records.some((r) => r.event.id === this.selected));
      button.classList.toggle('is-new', group.records.some((r) => r.isNew));
      const preview = previews.get(group);
      button.classList.toggle('has-preview', Boolean(preview));
      button.classList.toggle('compact-preview', compact);
      button.classList.toggle('show-label', index < 5 && !previewRects.some((r) => group.p.x + 32 > r.left && group.p.x + 100 < r.right && group.p.y > r.top - 12 && group.p.y < r.bottom + 12));
      if (preview) { button.style.setProperty('--preview-left', `${preview.left}px`); button.style.setProperty('--preview-top', `${preview.top}px`); }
      button.classList.toggle('is-high', importance(group.record.event) >= 80);
      button.children[0].textContent = count > 1 ? String(count) : '';
      button.children[1].children[0].textContent = `${group.record.location.name || '事件位置'}${count > 1 ? ` · ${count} 个事件` : ''}`;
      const titleChars = Array.from(String(group.record.event.title || ''));
      const maxChars = compact ? 38 : 58;
      button.children[1].children[1].textContent = titleChars.slice(0, maxChars).join('') + (titleChars.length > maxChars ? '…' : '');
      button.setAttribute('aria-label', count > 1 ? `${group.record.location.name || '此区域'}，${count} 个事件，重点：${group.record.event.title}。点击展开` : `${group.record.location.name || '事件位置'}：${group.record.event.title}`);
      button.title = group.record.event.title || '';
      button.style.transform = `translate(${group.p.x}px, ${group.p.y}px)`;
    });
    for (const el of existing.values()) el.remove();
  }

  animate(now) {
    this.raf = requestAnimationFrame(this.animate);
    if (document.hidden || now - (this.lastFrame || 0) < (this.reduced ? 100 : 32)) return;
    this.lastFrame = now;
    if (this.focusAnimation) {
      const t = Math.min(1, (now - this.focusAnimation.start) / 950);
      const ease = 1 - Math.pow(1 - t, 3);
      const from = this.focusAnimation.from, to = this.focusAnimation.to;
      const direction = from.clone().normalize().lerp(to.clone().normalize(), ease).normalize();
      this.camera.position.copy(direction.multiplyScalar(THREE.MathUtils.lerp(from.length(), to.length(), ease)));
      if (t >= 1) this.focusAnimation = null;
    }
    this.controls.update();
    if (now - (this.lastCluster || 0) > 250) { this.updateClusters(); this.lastCluster = now; }
    else for (const button of this.labels.children) {
      const p = this.project(button._group.record);
      button.style.visibility = p ? 'visible' : 'hidden';
      if (p) button.style.transform = `translate(${p.x}px, ${p.y}px)`;
    }
    this.renderer.render(this.scene, this.camera);
  }

  stop() { cancelAnimationFrame(this.raf); }
  destroy() {
    this.stop(); this.resizeObserver.disconnect(); this.controls.dispose();
    document.removeEventListener('visibilitychange', this.visibilityHandler);
    this.scene.traverse((obj) => { obj.geometry?.dispose(); if (obj.material) { obj.material.map?.dispose(); obj.material.dispose(); } });
    this.renderer.dispose(); this.renderer.domElement.remove(); this.labels.remove();
  }
}
