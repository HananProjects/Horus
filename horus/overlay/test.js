const fs = require("fs");
const log = (msg) => fs.appendFileSync("B:\\Horus\\horus\\horus\\overlay\\test.log", msg + "\n");

log("=== PROCESS PROPERTIES ===");
const keys = Object.getOwnPropertyNames(process)
  .filter(k => typeof process[k] !== "function")
  .sort();
for (const k of keys) {
  try {
    const v = process[k];
    if (typeof v === "object" && v !== null) {
      log(k + ": [object] keys=" + Object.keys(v).join(",").slice(0, 80));
    } else {
      log(k + ": " + String(v).slice(0, 80));
    }
  } catch (e) {
    log(k + ": [error]");
  }
}

log("=== BUILT-IN MODULES ===");
const Module = require("module");
log("builtinModules includes electron: " + Module.builtinModules.includes("electron"));
log("first 20 builtins: " + Module.builtinModules.slice(0, 20).join(", "));
