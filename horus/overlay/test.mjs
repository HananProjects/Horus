import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";

const log = (msg) => fs.appendFileSync("B:\\Horus\\horus\\horus\\overlay\\test.log", msg + "\n");

log("=== createRequire from asar test ===");

// Try: create a require function rooted in the asar package
// Electron's asar-aware module loader has the electron built-ins
const distDir = path.dirname(process.execPath);
const asarMain = path.join(distDir, "resources", "default_app.asar", "main.js");
log("asar path: " + asarMain);

try {
  const asarReq = createRequire(asarMain);
  const e = asarReq("electron");
  log("asarReq('electron') type: " + typeof e);
  if (typeof e === "object" && e !== null) {
    log("keys: " + Object.keys(e).join(", ").slice(0, 100));
    if (e.app) {
      log("HAS APP - ELECTRON WORKS VIA ASAR REQUIRE");
      e.app.whenReady().then(() => {
        log("app.whenReady fired!");
        e.app.quit();
      });
    }
  } else {
    log("value: " + String(e).slice(0, 80));
  }
} catch (err) {
  log("asarReq ERROR: " + err.message.slice(0, 120));
}

// Also try createRequire from the frontend directory (where electron npm pkg lives)
try {
  const frontendReq = createRequire("B:\\Horus\\horus\\horus\\frontend\\package.json");
  const e2 = frontendReq("electron");
  log("frontendReq type: " + typeof e2);
  if (typeof e2 === "object" && e2 !== null) {
    log("frontendReq keys: " + Object.keys(e2).join(", ").slice(0, 100));
  } else {
    log("frontendReq value: " + String(e2).slice(0, 80));
  }
} catch (err) {
  log("frontendReq ERROR: " + err.message.slice(0, 80));
}
