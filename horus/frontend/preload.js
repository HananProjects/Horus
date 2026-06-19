const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("electronAPI", {
  setClickable: (val) => ipcRenderer.send("set-clickable", val),
  openFullUI:   () => ipcRenderer.send("open-full-ui"),
  moveOverlay:  (x, y) => ipcRenderer.send("move-overlay", { x, y }),
  getOverlayPos: () => ipcRenderer.invoke("get-overlay-pos"),
});
