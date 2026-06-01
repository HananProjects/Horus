import { useEffect, useRef } from "react";
import * as THREE from "three";

const NODE_COUNT = 220;
const R = 1.2;
const CONNECT_DIST = 0.58;
const TRAVELER_COUNT = 60;
const MAX_TRAVELERS = 110;
const AMBIENT_COUNT = 75;    // floating particles scattered around the sphere
const AMBIENT_INNER = 1.45;  // min radius (just outside sphere)
const AMBIENT_OUTER = 2.4;   // max radius

function fibonacciSphere(n, r) {
  const pts = [];
  const phi = Math.PI * (3 - Math.sqrt(5));
  for (let i = 0; i < n; i++) {
    const y = 1 - (i / (n - 1)) * 2;
    const rxy = Math.sqrt(Math.max(0, 1 - y * y));
    const theta = phi * i;
    pts.push(new THREE.Vector3(r * rxy * Math.cos(theta), r * y, r * rxy * Math.sin(theta)));
  }
  return pts;
}

function randomShellPoint(innerR, outerR) {
  const r = innerR + Math.random() * (outerR - innerR);
  const theta = Math.random() * Math.PI * 2;
  const phi = Math.acos(2 * Math.random() - 1);
  return new THREE.Vector3(
    r * Math.sin(phi) * Math.cos(theta),
    r * Math.sin(phi) * Math.sin(theta),
    r * Math.cos(phi),
  );
}

export default function NeuralSphere({ status, nodeCount = 0 }) {
  const mountRef = useRef(null);
  const statusRef = useRef(status);
  const nodeCountRef = useRef(nodeCount);

  useEffect(() => { statusRef.current = status; }, [status]);
  useEffect(() => { nodeCountRef.current = nodeCount; }, [nodeCount]);

  useEffect(() => {
    const el = mountRef.current;
    if (!el) return;

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(50, 1, 0.1, 100);
    camera.position.z = 4;

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    el.appendChild(renderer.domElement);

    function resize() {
      const w = el.clientWidth, h = el.clientHeight;
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    }
    resize();

    // ── Sphere nodes ──────────────────────────────────────────────────────────
    const nodes = fibonacciSphere(NODE_COUNT, R);

    const nodeGeo = new THREE.BufferGeometry().setFromPoints(nodes);
    const nodeMat = new THREE.PointsMaterial({
      color: 0xf59e0b,
      size: 0.042,
      transparent: true,
      opacity: 0.85,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });
    const nodeCloud = new THREE.Points(nodeGeo, nodeMat);

    // ── Sphere connections ────────────────────────────────────────────────────
    const lineVerts = [];
    const linePairs = [];
    for (let i = 0; i < nodes.length; i++) {
      for (let j = i + 1; j < nodes.length; j++) {
        if (nodes[i].distanceTo(nodes[j]) < CONNECT_DIST) {
          lineVerts.push(nodes[i].x, nodes[i].y, nodes[i].z, nodes[j].x, nodes[j].y, nodes[j].z);
          linePairs.push([i, j]);
        }
      }
    }
    const lineGeo = new THREE.BufferGeometry();
    lineGeo.setAttribute("position", new THREE.Float32BufferAttribute(lineVerts, 3));
    const lineMat = new THREE.LineBasicMaterial({
      color: 0xd97706,
      transparent: true,
      opacity: 0.22,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });
    const lineSegs = new THREE.LineSegments(lineGeo, lineMat);

    // ── Ambient floating particles (the "space" around the sphere) ────────────
    const ambientPts = Array.from({ length: AMBIENT_COUNT }, () =>
      randomShellPoint(AMBIENT_INNER * R, AMBIENT_OUTER * R)
    );

    const ambGeo = new THREE.BufferGeometry().setFromPoints(ambientPts);
    const ambMat = new THREE.PointsMaterial({
      color: 0xfbbf24,
      size: 0.032,
      transparent: true,
      opacity: 0.45,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });
    const ambCloud = new THREE.Points(ambGeo, ambMat);

    // ── Ambient connection lines (ambient ↔ nearest sphere node) ─────────────
    const extLineVerts = [];
    for (const ap of ambientPts) {
      let nearest = nodes[0];
      let minD = Infinity;
      for (const n of nodes) {
        const d = ap.distanceTo(n);
        if (d < minD) { minD = d; nearest = n; }
      }
      // Only draw if not too far — creates sparse "reaching" lines
      if (minD < 1.1) {
        extLineVerts.push(ap.x, ap.y, ap.z, nearest.x, nearest.y, nearest.z);
      }
    }
    // Also connect some ambient pairs that are close to each other
    for (let i = 0; i < ambientPts.length; i++) {
      for (let j = i + 1; j < ambientPts.length; j++) {
        if (ambientPts[i].distanceTo(ambientPts[j]) < 0.7) {
          extLineVerts.push(
            ambientPts[i].x, ambientPts[i].y, ambientPts[i].z,
            ambientPts[j].x, ambientPts[j].y, ambientPts[j].z,
          );
        }
      }
    }
    const extLineGeo = new THREE.BufferGeometry();
    extLineGeo.setAttribute("position", new THREE.Float32BufferAttribute(extLineVerts, 3));
    const extLineMat = new THREE.LineBasicMaterial({
      color: 0xd97706,
      transparent: true,
      opacity: 0.07,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });
    const extLineSegs = new THREE.LineSegments(extLineGeo, extLineMat);

    // ── Traveling particles along sphere connections ───────────────────────────
    const travPos = new Float32Array(MAX_TRAVELERS * 3);
    const travGeo = new THREE.BufferGeometry();
    travGeo.setAttribute("position", new THREE.BufferAttribute(travPos, 3));
    const travMat = new THREE.PointsMaterial({
      color: 0xfde68a,
      size: 0.065,
      transparent: true,
      opacity: 1.0,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });
    const travCloud = new THREE.Points(travGeo, travMat);

    const travState = Array.from({ length: MAX_TRAVELERS }, () => ({
      pair: linePairs[Math.floor(Math.random() * linePairs.length)],
      t: Math.random(),
      dir: Math.random() < 0.5 ? 1 : -1,
    }));

    // ── Center core ───────────────────────────────────────────────────────────
    const coreMat = new THREE.MeshBasicMaterial({
      color: 0xfbbf24,
      transparent: true,
      opacity: 0.75,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });
    const core = new THREE.Mesh(new THREE.SphereGeometry(0.065, 12, 8), coreMat);

    // ── Equatorial halo ring ──────────────────────────────────────────────────
    const haloMat = new THREE.MeshBasicMaterial({
      color: 0xf59e0b,
      transparent: true,
      opacity: 0.18,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });
    const halo = new THREE.Mesh(new THREE.TorusGeometry(R * 0.48, 0.005, 4, 64), haloMat);
    halo.rotation.x = Math.PI / 2;

    // Group: sphere content rotates together; ambient doesn't
    const sphereGroup = new THREE.Group();
    sphereGroup.add(lineSegs, nodeCloud, travCloud, core, halo);

    const ambientGroup = new THREE.Group();
    ambientGroup.add(ambCloud, extLineSegs);

    scene.add(sphereGroup, ambientGroup);

    // ── Animation ─────────────────────────────────────────────────────────────
    let raf;
    let clock = 0;

    let smoothNOp = 0.75;
    let smoothLOp = 0.20;
    let smoothScale = 1.0;
    let smoothCoreOp = 0.5;
    let smoothCoreScale = 1.0;
    let smoothAmbOp = 0.40;

    function lerp(a, b, t) { return a + (b - a) * t; }

    function animate() {
      raf = requestAnimationFrame(animate);
      clock += 0.016;

      const st = statusRef.current;
      const nc = nodeCountRef.current;
      const active = st !== "idle";
      const thinking = st === "thinking" || st === "processing";
      const speaking = st === "speaking";
      const listening = st === "listening";
      const complexity = Math.min(nc / 5, 1);

      // Scale / breathing
      let targetScale;
      if (speaking) {
        const envelope = (Math.sin(clock * 3.1) * 0.4 + Math.sin(clock * 5.3) * 0.35 + Math.sin(clock * 2.0) * 0.25 + 1) / 2;
        targetScale = 1 + envelope * 0.018;
      } else {
        targetScale = 1 + Math.sin(clock * (active ? 2.2 : 1.0)) * (active ? 0.032 : 0.016);
      }
      smoothScale = lerp(smoothScale, targetScale, 0.06);
      sphereGroup.scale.setScalar(smoothScale);

      // Rotation
      const rSpeed = thinking ? 0.0025 : active ? 0.0014 : 0.0005;
      sphereGroup.rotation.y += rSpeed;
      sphereGroup.rotation.x += rSpeed * 0.28;

      // Ambient drifts very slowly in the opposite direction for parallax feel
      ambientGroup.rotation.y -= rSpeed * 0.18;
      ambientGroup.rotation.x += rSpeed * 0.09;

      // Node / line opacity
      const baseNOp = 0.72 + complexity * 0.18;
      const baseLOp = 0.18 + complexity * 0.14;
      let targetNOp = baseNOp;
      let targetLOp = baseLOp;
      if (speaking) {
        const glow = (Math.sin(clock * 2.8) + 1) * 0.5;
        targetNOp = baseNOp + glow * 0.08;
        targetLOp = baseLOp + glow * 0.07;
      } else if (thinking) {
        targetNOp = baseNOp + 0.12;
        targetLOp = baseLOp + 0.14;
      } else if (listening) {
        targetNOp = baseNOp + 0.06;
        targetLOp = baseLOp + 0.07;
      }
      smoothNOp = lerp(smoothNOp, targetNOp, 0.04);
      smoothLOp = lerp(smoothLOp, targetLOp, 0.04);
      nodeMat.opacity = smoothNOp;
      lineMat.opacity = smoothLOp;

      // Ambient opacity — subtly breathes opposite to sphere
      const targetAmbOp = 0.30 + complexity * 0.15 + (active ? 0.08 : 0) + Math.sin(clock * 0.7) * 0.04;
      smoothAmbOp = lerp(smoothAmbOp, targetAmbOp, 0.03);
      ambMat.opacity = smoothAmbOp;
      extLineMat.opacity = smoothAmbOp * 0.18;

      // Core
      const cpRate = speaking ? 2.8 : active ? 2.0 : 0.9;
      const targetCoreOp = 0.4 + (Math.sin(clock * cpRate) + 1) * 0.25;
      const targetCoreScale = 1 + (Math.sin(clock * cpRate) + 1) * 0.05 * (active ? 1.2 : 0.6);
      smoothCoreOp = lerp(smoothCoreOp, targetCoreOp, 0.05);
      smoothCoreScale = lerp(smoothCoreScale, targetCoreScale, 0.05);
      coreMat.opacity = smoothCoreOp;
      core.scale.setScalar(smoothCoreScale);

      // Halo
      halo.rotation.z += 0.0007;
      haloMat.opacity = lerp(haloMat.opacity, 0.12 + complexity * 0.16 + (active ? 0.06 : 0), 0.03);

      // Travelers
      const tSpeed = thinking ? 0.005 : active ? 0.003 : 0.0012;
      const activeTravelers = Math.min(Math.floor(TRAVELER_COUNT * (1 + complexity * 0.8)), MAX_TRAVELERS);
      for (let i = 0; i < activeTravelers; i++) {
        const s = travState[i];
        s.t += tSpeed * s.dir;
        if (s.t > 1 || s.t < 0) {
          s.dir *= -1;
          s.t = Math.max(0, Math.min(1, s.t));
          if (Math.random() < 0.35) {
            s.pair = linePairs[Math.floor(Math.random() * linePairs.length)];
          }
        }
        const [ai, bi] = s.pair;
        const v = nodes[ai].clone().lerp(nodes[bi], s.t);
        travPos[i * 3] = v.x; travPos[i * 3 + 1] = v.y; travPos[i * 3 + 2] = v.z;
      }
      travGeo.attributes.position.needsUpdate = true;

      renderer.render(scene, camera);
    }

    animate();

    const ro = new ResizeObserver(() => requestAnimationFrame(resize));
    ro.observe(el);

    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
      renderer.dispose();
      if (renderer.domElement.parentNode === el) el.removeChild(renderer.domElement);
    };
  }, []);

  return <div ref={mountRef} style={{ width: "100%", height: "100%" }} />;
}
