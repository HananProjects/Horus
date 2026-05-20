import { useEffect, useRef } from "react";
import * as THREE from "three";

const NODE_COUNT = 180;
const R = 1.2;
const CONNECT_DIST = 0.62;
const TRAVELER_COUNT = 55;
const MAX_TRAVELERS = 100;

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

    // --- Geometry ---
    const nodes = fibonacciSphere(NODE_COUNT, R);

    // Node cloud
    const nodeGeo = new THREE.BufferGeometry().setFromPoints(nodes);
    const nodeMat = new THREE.PointsMaterial({
      color: 0xf59e0b,
      size: 0.045,
      transparent: true,
      opacity: 0.85,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });
    const nodeCloud = new THREE.Points(nodeGeo, nodeMat);

    // Connections
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
      opacity: 0.2,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });
    const lineSegs = new THREE.LineSegments(lineGeo, lineMat);

    // Faint bounding wireframe
    const wireMat = new THREE.MeshBasicMaterial({
      color: 0x92400e,
      wireframe: true,
      transparent: true,
      opacity: 0.055,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });
    const wireframe = new THREE.Mesh(new THREE.SphereGeometry(R * 1.01, 24, 16), wireMat);

    // Traveling particles along connections
    const travPos = new Float32Array(MAX_TRAVELERS * 3);
    const travGeo = new THREE.BufferGeometry();
    travGeo.setAttribute("position", new THREE.BufferAttribute(travPos, 3));
    const travMat = new THREE.PointsMaterial({
      color: 0xfde68a,
      size: 0.06,
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

    // Center core
    const coreMat = new THREE.MeshBasicMaterial({
      color: 0xfbbf24,
      transparent: true,
      opacity: 0.75,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });
    const core = new THREE.Mesh(new THREE.SphereGeometry(0.07, 12, 8), coreMat);

    // Equatorial halo ring
    const haloMat = new THREE.MeshBasicMaterial({
      color: 0xf59e0b,
      transparent: true,
      opacity: 0.2,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });
    const halo = new THREE.Mesh(new THREE.TorusGeometry(R * 0.48, 0.006, 4, 64), haloMat);
    halo.rotation.x = Math.PI / 2;

    const group = new THREE.Group();
    group.add(wireframe, lineSegs, nodeCloud, travCloud, core, halo);
    scene.add(group);

    // --- Animation ---
    let raf;
    let clock = 0;

    // Smoothed values for soft blending between states
    let smoothNOp = 0.75;
    let smoothLOp = 0.18;
    let smoothScale = 1.0;
    let smoothCoreOp = 0.5;
    let smoothCoreScale = 1.0;

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

      // Target scale — breathing when idle/thinking, very gentle flutter when speaking
      let targetScale;
      if (speaking) {
        // Slow, low-amplitude mix — just a shimmer, not a bounce
        const s1 = Math.sin(clock * 3.1) * 0.4;
        const s2 = Math.sin(clock * 5.3) * 0.35;
        const s3 = Math.sin(clock * 2.0) * 0.25;
        const envelope = (s1 + s2 + s3 + 1) / 2;
        targetScale = 1 + envelope * 0.018; // max ~1.8% change
      } else {
        const bRate = active ? 2.2 : 1.0;
        const bAmp = active ? 0.032 : 0.016;
        targetScale = 1 + Math.sin(clock * bRate) * bAmp;
      }
      smoothScale = lerp(smoothScale, targetScale, 0.06);
      group.scale.setScalar(smoothScale);

      // Rotation — slow always
      const rSpeed = thinking ? 0.0025 : active ? 0.0014 : 0.0005;
      group.rotation.y += rSpeed;
      group.rotation.x += rSpeed * 0.28;

      // Target opacities
      const baseNOp = 0.72 + complexity * 0.18;
      const baseLOp = 0.16 + complexity * 0.16;

      let targetNOp = baseNOp;
      let targetLOp = baseLOp;

      if (speaking) {
        // Subtle glow rhythm — barely noticeable but present
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

      // Core — soft pulse, barely grows
      const cpRate = speaking ? 2.8 : active ? 2.0 : 0.9;
      const targetCoreOp = 0.4 + (Math.sin(clock * cpRate) + 1) * 0.25;
      const targetCoreScale = 1 + (Math.sin(clock * cpRate) + 1) * 0.05 * (active ? 1.2 : 0.6);
      smoothCoreOp = lerp(smoothCoreOp, targetCoreOp, 0.05);
      smoothCoreScale = lerp(smoothCoreScale, targetCoreScale, 0.05);
      coreMat.opacity = smoothCoreOp;
      core.scale.setScalar(smoothCoreScale);

      // Halo
      halo.rotation.z += 0.0007;
      haloMat.opacity = lerp(haloMat.opacity, 0.13 + complexity * 0.18 + (active ? 0.07 : 0), 0.03);

      // Travelers — more particles as more nodes added
      const tSpeed = thinking ? 0.005 : active ? 0.003 : 0.001;
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
        travPos[i * 3] = v.x;
        travPos[i * 3 + 1] = v.y;
        travPos[i * 3 + 2] = v.z;
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
