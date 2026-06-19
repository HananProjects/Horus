# Horus — Google Earth Viewer Handoff

## Project Context

**Horus** is a personal AI assistant with a sci-fi HUD interface. It has:
- **Frontend**: React app at `horus/frontend/` (CRA, runs on `localhost:3000`)
- **Backend**: FastAPI + Python at `horus/backend/` (runs on `localhost:8000`), file is `brain.py`
- **Voice I/O**: ElevenLabs TTS + microphone STT
- **Visual panels**: Draggable HUD windows for stocks, images, scores, maps, etc.

The user is **Hanan**, based in Saskatoon, Saskatchewan, Canada.

---

## What Was Built: Google Earth Viewer

When Horus is asked about any location ("show me Edmonton", "directions to Vancouver"), the backend triggers a **map panel** that opens a full-screen globe experience.

### Two-Phase Experience

**Phase 1 — globe.gl (0–3s)**
- A 3D WebGL Earth globe (`earth-night.jpg` texture with city lights, star field background)
- Geocodes the location → flies the camera in from high altitude (2.5 Earth radii) down to the target (0.35 altitude) over 2.8 seconds
- Shows a pulsing cyan ring marker + glowing dot at the target location
- Fully interactive (drag to spin)

**Phase 2 — Google Maps JS (after fly-in)**
- Crossfades (1.4s opacity transition) from the globe into Google Maps JavaScript API
- Regular locations: `zoom: 17, tilt: 45, mapTypeId: "hybrid"` — 3D angled satellite view with streets (Google Earth style)
- Directions mode: `zoom: 10, tilt: 0` with `DirectionsService` + `DirectionsRenderer` showing the full driving route

---

## Key Files

### `horus/frontend/src/components/GlobeViewer.jsx`
The main component. Full self-contained — handles both phases, geocoding, Maps JS loading, and HUD chrome (corner brackets, label, close button, ESC key).

**Key functions:**
- `geocode(query, apiKey)` — Uses Google Geocoding API first (accurate), falls back to Nominatim if no key
- `loadMapsScript(apiKey)` — Dynamically loads Maps JS SDK with proper callback pattern (`callback=__horusMapsReady`), detects `gm_authFailure`
- Phase state machine: `"loading" → "globe" → "transition" → "map"` (or stays on `"globe"` if no API key)

**Directions mode detection:** reads `panel.map_mode === "directions"` and `panel.origin` / `panel.destination` from panel data.

### `horus/frontend/src/components/HudPanel.jsx`
Routes map panels to `<GlobeViewer>` when `panel.content_type === "map"`. All other visual types go to `<VisualPanel>`.

### `horus/backend/brain.py`
- `GOOGLE_MAPS_API_KEY` loaded from `.env`
- `_build_maps_url(inp)` builds Google Maps Embed URLs (used as fallback reference)
- In the `show_visual` tool handler, map panels get these fields in `panel_data`:
  ```python
  panel_data["url"]         = _build_maps_url(inp)      # embed URL (fallback)
  panel_data["api_key"]     = GOOGLE_MAPS_API_KEY        # for Maps JS + Geocoding
  panel_data["map_mode"]    = inp.get("map_mode", "place")
  panel_data["location"]    = inp.get("location") or inp.get("destination") or inp.get("title", "")
  panel_data["origin"]      = inp.get("origin")          # directions only
  panel_data["destination"] = inp.get("destination")     # directions only
  ```

### `horus/backend/.env`
```
GOOGLE_MAPS_API_KEY=AIzaSyANlOVpcJAin2P5Lg4wQn8p56BP4alKcH0
```

---

## Dependencies

**Frontend** (`horus/frontend/package.json`):
- `globe.gl@^2.46.1` — 3D WebGL globe (vanilla JS, dynamically imported in useEffect)

**Google Cloud APIs enabled** (project: `horus-496801`):
- Maps JavaScript API ✅
- Maps Embed API ✅
- Aerial View API ✅
- Places API ✅
- Roads API ✅
- Routes API ✅
- Street View Static API ✅
- Geocoding API — **needs to be added** if not done yet
- Directions API — **needs to be added** if not done yet

---

## Backend Tool Definition

The AI uses `show_visual` with `content_type="map"` to trigger the viewer. Relevant fields:

```json
{
  "content_type": "map",
  "title": "Edmonton, Alberta",
  "location": "Edmonton, Alberta",
  "map_mode": "place",        // or "satellite", "search", "directions"
  "origin": "Saskatoon, SK",  // directions mode only
  "destination": "Edmonton",  // directions mode only
  "zoom": 16                  // optional
}
```

Map modes:
- `place` — specific location, zoom 17, tilt 45, hybrid satellite
- `satellite` — same as place but emphasizes overhead view
- `search` — find nearby places
- `directions` — driving route from origin to destination, zoom 10, flat

---

## Known Issues / What Was Fixed

| Issue | Fix |
|-------|-----|
| Map showed in Mali, Africa when asking for "Edmonton" | Switched geocoding from Nominatim to Google Geocoding API (same key) |
| Only 2D flat map showing | Replaced Maps Embed iframe with globe.gl + Maps JS API two-phase approach |
| Directions not showing route | Backend now passes `origin`/`destination` in panel_data; frontend uses `DirectionsService` |
| API key not available to Maps JS loader | Backend now sends `api_key` directly in panel_data |
| Maps JS script loading race condition | Fixed by using `callback=__horusMapsReady` parameter instead of `onload` |

---

## Current State (as of 2026-06-03)

- Branch: `googleearth`
- Last commit: `7ab9089` — "Add Google Earth 3D globe viewer with Maps JS street-level fallback"
- Globe fly-in works ✅
- Maps JS crossfade implemented ✅
- Directions mode implemented ✅
- Geocoding fixed ✅
- Still needs: Geocoding API + Directions API enabled in Google Cloud Console to be fully tested end-to-end

---

## How to Run

```powershell
# Backend
cd horus/backend
.\venv\Scripts\uvicorn.exe main:app --reload

# Frontend
cd horus/frontend
npm start
```

Or use the convenience script:
```powershell
.\scripts\start-backend.ps1
```
