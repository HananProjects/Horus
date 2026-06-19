const { app, BrowserWindow, ipcMain, shell } = require("electron");
const path = require("path");
const isDev = process.env.ELECTRON_DEV === "true";

let overlayWin;

app.whenReady().then(() => {
  const { screen } = require("electron");
  const { width, height } = screen.getPrimaryDisplay().workAreaSize;

  overlayWin = new BrowserWindow({
    width: 180,
    height: 180,
    x: width - 210,
    y: height - 210,
    transparent: true,
    frame: false,
    alwaysOnTop: true,
    skipTaskbar: true,
    resizable: false,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  overlayWin.setIgnoreMouseEvents(true, { forward: true });
  overlayWin.webContents.openDevTools({ mode: "detach" }); // debug

  if (isDev) {
    overlayWin.loadURL("http://localhost:3000?overlay=true");
  } else {
    overlayWin.loadFile(
      path.join(__dirname, "..", "frontend", "build", "index.html"),
      { query: { overlay: "true" } }
    );
  }

  ipcMain.on("set-clickable", (_e, clickable) => {
    if (!overlayWin) return;
    overlayWin.setIgnoreMouseEvents(!clickable, { forward: true });
  });

  ipcMain.on("open-full-ui", () => {
    shell.openExternal("http://localhost:3000");
  });

  ipcMain.on("move-overlay", (_e, { x, y }) => {
    if (overlayWin) overlayWin.setPosition(Math.round(x), Math.round(y));
  });

  ipcMain.handle("get-overlay-pos", () => {
    return overlayWin ? overlayWin.getPosition() : [0, 0];
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});
