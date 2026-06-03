import { useEffect, useRef, useState } from "react";

function Corner({ style }) {
  return <div style={{ position: "absolute", width: 20, height: 20, pointerEvents: "none", zIndex: 63, ...style }} />;
}

async function geocode(query, apiKey) {
  // Google Geocoding API — accurate, uses same key we already have
  if (apiKey) {
    try {
      const res = await fetch(
        `https://maps.googleapis.com/maps/api/geocode/json?address=${encodeURIComponent(query)}&key=${apiKey}`
      );
      const data = await res.json();
      if (data.results?.length) {
        const { lat, lng } = data.results[0].geometry.location;
        return { lat, lng };
      }
    } catch {}
  }
  // Fallback: Nominatim
  try {
    const res = await fetch(
      `https://nominatim.openstreetmap.org/search?q=${encodeURIComponent(query)}&format=json&limit=1`,
      { headers: { "User-Agent": "HorusApp/1.0" } }
    );
    const data = await res.json();
    if (data.length) return { lat: parseFloat(data[0].lat), lng: parseFloat(data[0].lon) };
  } catch {}
  return { lat: 20, lng: 0 };
}

function loadMapsScript(apiKey) {
  return new Promise((resolve, reject) => {
    if (window.google?.maps?.Map) { resolve(); return; }

    const old = document.querySelector("script[data-horus-maps]");
    if (old) old.remove();
    delete window.google;

    const cbName = "__horusMapsReady";
    window[cbName] = () => { delete window[cbName]; resolve(); };
    window.gm_authFailure = () => reject(new Error("auth"));

    const s = document.createElement("script");
    s.setAttribute("data-horus-maps", "1");
    s.src = `https://maps.googleapis.com/maps/api/js?key=${apiKey}&callback=${cbName}&v=beta&loading=async`;
    s.onerror = () => reject(new Error("network"));
    document.head.appendChild(s);
  });
}

export default function GlobeViewer({ panel, onDismiss }) {
  const globeContainerRef = useRef(null);
  const mapContainerRef   = useRef(null);
  const globeRef          = useRef(null);
  // loading → globe → transition → map  (stays on globe if no key)
  const [phase, setPhase] = useState("loading");

  const location   = panel.location || panel.title || "";
  const label      = (location || "LIVE VIEW").toUpperCase();
  const apiKey     = panel.api_key || "";
  const mapMode    = panel.map_mode || "place";
  const isDirections = mapMode === "directions";

  useEffect(() => {
    let cancelled = false;

    (async () => {
      // For globe fly-in, geocode the destination (or location for non-directions)
      const geocodeTarget = isDirections ? (panel.destination || location) : location;
      const { lat, lng } = await geocode(geocodeTarget, apiKey);
      if (cancelled || !globeContainerRef.current) return;

      // ── Phase 1: globe.gl fly-in ──────────────────────────────────
      const { default: Globe } = await import("globe.gl");
      if (cancelled || !globeContainerRef.current) return;

      const W = globeContainerRef.current.offsetWidth;
      const H = globeContainerRef.current.offsetHeight;
      const marker = { lat, lng, maxR: 3, propagationSpeed: 2, repeatPeriod: 900 };

      const globe = Globe()(globeContainerRef.current);
      globe
        .width(W).height(H)
        .backgroundColor("#000000")
        .backgroundImageUrl("//unpkg.com/three-globe/example/img/night-sky.png")
        .globeImageUrl("//unpkg.com/three-globe/example/img/earth-night.jpg")
        .bumpImageUrl("//unpkg.com/three-globe/example/img/earth-topology.png")
        .atmosphereColor("#1a4a8a")
        .atmosphereAltitude(0.28)
        .ringsData([marker])
        .ringColor(() => "#00e5ff")
        .ringMaxRadius("maxR")
        .ringPropagationSpeed("propagationSpeed")
        .ringRepeatPeriod("repeatPeriod")
        .pointsData([{ lat, lng }])
        .pointColor(() => "#00e5ff")
        .pointAltitude(0.01)
        .pointRadius(0.35);

      globeRef.current = globe;
      globe.pointOfView({ lat, lng, altitude: 2.5 });
      setPhase("globe");

      await new Promise(r => setTimeout(r, 200));
      if (cancelled) return;
      globe.pointOfView({ lat, lng, altitude: 0.35 }, 2800);

      if (!apiKey) return; // stay on globe if no key

      await new Promise(r => setTimeout(r, 3200));
      if (cancelled) return;

      // ── Phase 2: Google Maps JS ───────────────────────────────────
      setPhase("transition");

      try {
        await loadMapsScript(apiKey);
        if (cancelled || !mapContainerRef.current) return;

        const mapOptions = isDirections
          ? { center: { lat, lng }, zoom: 10, tilt: 0,  mapTypeId: "hybrid", mapId: "DEMO_MAP_ID", gestureHandling: "greedy", fullscreenControl: false, streetViewControl: false, mapTypeControl: false, zoomControl: true, scaleControl: true }
          : { center: { lat, lng }, zoom: 17, tilt: 45, mapTypeId: "hybrid", mapId: "DEMO_MAP_ID", rotateControl: true, gestureHandling: "greedy", fullscreenControl: false, streetViewControl: true, mapTypeControl: false, zoomControl: true, scaleControl: true };

        const map = new window.google.maps.Map(mapContainerRef.current, mapOptions);

        if (isDirections && panel.origin && panel.destination) {
          // Show a driving route
          const directionsService  = new window.google.maps.DirectionsService();
          const directionsRenderer = new window.google.maps.DirectionsRenderer({ map });
          directionsService.route(
            { origin: panel.origin, destination: panel.destination, travelMode: window.google.maps.TravelMode.DRIVING },
            (result, status) => { if (status === "OK") directionsRenderer.setDirections(result); }
          );
        } else {
          // Drop a marker
          await window.google.maps.importLibrary("marker");
          new window.google.maps.marker.AdvancedMarkerElement({ position: { lat, lng }, map, title: location });
        }

        setPhase("map");
      } catch (err) {
        console.error("[Horus] Maps JS failed:", err.message);
        setPhase("globe");
      }
    })();

    return () => { cancelled = true; globeRef.current = null; };
  }, []); // init once

  useEffect(() => {
    const onResize = () => {
      if (globeRef.current && globeContainerRef.current) {
        globeRef.current
          .width(globeContainerRef.current.offsetWidth)
          .height(globeContainerRef.current.offsetHeight);
      }
    };
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  useEffect(() => {
    const onKey = (e) => { if (e.key === "Escape") onDismiss(panel.id); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [panel.id, onDismiss]);

  const showMap   = phase === "map";
  const showGlobe = phase !== "map";

  return (
    <div style={{ position: "fixed", inset: 0, zIndex: 62, background: "#000" }}>

      {/* Globe layer */}
      <div
        ref={globeContainerRef}
        style={{
          position: "absolute", inset: 0,
          opacity: showGlobe ? 1 : 0,
          transition: "opacity 1.4s ease",
          pointerEvents: showGlobe ? "auto" : "none",
        }}
      />

      {/* Maps layer — always in DOM so SDK can measure it */}
      <div
        ref={mapContainerRef}
        style={{
          position: "absolute", inset: 0,
          opacity: showMap ? 1 : 0,
          transition: "opacity 1.4s ease",
        }}
      />

      {phase === "loading" && (
        <div style={{
          position: "absolute", inset: 0, zIndex: 64, background: "#000",
          display: "flex", alignItems: "center", justifyContent: "center",
          pointerEvents: "none",
        }}>
          <span style={{
            fontFamily: "monospace", fontSize: "0.6rem",
            letterSpacing: "0.35em", color: "rgba(0,229,255,0.55)", textTransform: "uppercase",
          }}>
            INITIALIZING EARTH...
          </span>
        </div>
      )}

      {phase === "transition" && (
        <div style={{
          position: "absolute", bottom: 56, left: "50%", transform: "translateX(-50%)",
          zIndex: 64, pointerEvents: "none",
        }}>
          <span style={{
            fontFamily: "monospace", fontSize: "0.48rem",
            letterSpacing: "0.28em", color: "rgba(0,229,255,0.4)", textTransform: "uppercase",
          }}>
            {isDirections ? "CALCULATING ROUTE..." : "ACQUIRING STREET FEED..."}
          </span>
        </div>
      )}

      {/* HUD chrome */}
      <Corner style={{ top: 10, left: 10, borderTop: "1px solid rgba(0,229,255,0.3)", borderLeft: "1px solid rgba(0,229,255,0.3)" }} />
      <Corner style={{ top: 10, right: 10, borderTop: "1px solid rgba(0,229,255,0.3)", borderRight: "1px solid rgba(0,229,255,0.3)" }} />
      <Corner style={{ bottom: 10, left: 10, borderBottom: "1px solid rgba(0,229,255,0.3)", borderLeft: "1px solid rgba(0,229,255,0.3)" }} />
      <Corner style={{ bottom: 10, right: 10, borderBottom: "1px solid rgba(0,229,255,0.3)", borderRight: "1px solid rgba(0,229,255,0.3)" }} />

      <div style={{
        position: "absolute", top: 18, left: 22, zIndex: 63,
        background: "rgba(0,0,0,0.65)", border: "1px solid rgba(0,229,255,0.22)",
        color: "rgba(0,229,255,0.75)", fontFamily: "monospace", fontSize: "0.55rem",
        letterSpacing: "0.28em", padding: "5px 12px",
        textTransform: "uppercase", backdropFilter: "blur(6px)", pointerEvents: "none",
      }}>
        {isDirections ? `ROUTE · ${label}` : `EARTH · ${label}`}
      </div>

      <button
        onClick={() => onDismiss(panel.id)}
        style={{
          position: "absolute", top: 18, right: 22, zIndex: 63,
          background: "rgba(0,0,0,0.65)", border: "1px solid rgba(0,229,255,0.3)",
          color: "#00e5ff", fontFamily: "monospace", fontSize: "0.6rem",
          letterSpacing: "0.2em", padding: "5px 14px",
          cursor: "pointer", textTransform: "uppercase",
          backdropFilter: "blur(6px)", transition: "border-color 0.2s, color 0.2s",
        }}
        onMouseEnter={e => { e.currentTarget.style.borderColor = "rgba(0,229,255,0.8)"; e.currentTarget.style.color = "#fff"; }}
        onMouseLeave={e => { e.currentTarget.style.borderColor = "rgba(0,229,255,0.3)"; e.currentTarget.style.color = "#00e5ff"; }}
      >
        ✕ CLOSE
      </button>

      <div style={{
        position: "absolute", bottom: 18, right: 22, zIndex: 63,
        color: "rgba(0,229,255,0.28)", fontFamily: "monospace",
        fontSize: "0.42rem", letterSpacing: "0.2em", pointerEvents: "none",
      }}>
        ESC TO EXIT
      </div>
    </div>
  );
}
