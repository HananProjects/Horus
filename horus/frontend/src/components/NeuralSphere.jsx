import { useEffect, useRef } from "react";
import * as THREE from "three";

const NODE_COUNT = 180;
const R = 1.2;
const CONNECT_DIST = 0.62;
const TRAVELER_COUNT = 55;

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

export default function NeuralSphere({ status }) {
  const mountRef = useRef(null);
  const statusRef = useRef(status);

  useEffect(() => { statusRef.current = status; }, [status]);

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
    const travPos = new Float32Array(TRAVELER_COUNT * 3);
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

    const travState = Array.from({ length: TRAVELER_COUNT }, () => ({
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

    function animate() {
      raf = requestAnimationFrame(animate);
      clock += 0.016;

      const st = statusRef.current;
      const active = st !== "idle";
      const thinking = st === "thinking" || st === "processing";
      const speaking = st === "speaking";
      const listening = st === "listening";

      // Breathing scale
      const bRate = active ? 2.2 : 1.0;
      const bAmp = active ? 0.04 : 0.018;
      group.scale.setScalar(1 + Math.sin(clock * bRate) * bAmp);

      // Rotation
      const rSpeed = thinking ? 0.003 : active ? 0.0018 : 0.0006;
      group.rotation.y += rSpeed;
      group.rotation.x += rSpeed * 0.28;

      // Node / line opacity driven by state
      let nOp = 0.78;
      let lOp = 0.18;
      if (speaking) {
        const pulse = (Math.sin(clock * 4) + 1) * 0.5;
        nOp = 0.65 + pulse * 0.35;
        lOp = 0.12 + pulse * 0.38;
      } else if (thinking) {
        nOp = 0.95;
        lOp = 0.38;
      } else if (listening) {
        nOp = 0.88;
        lOp = 0.27;
      }
      nodeMat.opacity = nOp;
      lineMat.opacity = lOp;

      // Core pulse
      const cp = (Math.sin(clock * (active ? 2.5 : 1.0)) + 1) * 0.5;
      coreMat.opacity = 0.45 + cp * 0.55;
      core.scale.setScalar(1 + cp * (active ? 0.35 : 0.15));

      // Halo
      halo.rotation.z += 0.0008;
      haloMat.opacity = active ? 0.38 : 0.18;

      // Travelers
      const tSpeed = thinking ? 0.005 : active ? 0.003 : 0.001;
      for (let i = 0; i < TRAVELER_COUNT; i++) {
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
