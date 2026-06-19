"""
Horus desktop overlay — floating eye that sits at low opacity when idle,
pulses when speaking/thinking, and opens the full UI on click.
"""
import tkinter as tk
from tkinter import Canvas
import ctypes
import ctypes.wintypes
import threading
import asyncio
import websockets
import json
import math
import webbrowser
from PIL import Image, ImageDraw, ImageTk

# ─── Eye drawing ─────────────────────────────────────────────────────────────

def draw_horus_eye(size: int, state: str, t: float, hovered: bool) -> Image.Image:
    W = H = size
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    cx, cy = W // 2, H // 2

    # Animation scale / glow
    if state == "speaking":
        scale = 1.0 + 0.04 * math.sin(t * 8)
        glow  = int(220 + 35 * math.sin(t * 8))
    elif state == "thinking":
        scale = 1.0 + 0.03 * math.sin(t * 3)
        glow  = int(160 + 60 * math.sin(t * 3))
    else:
        scale = 1.0 + 0.025 * math.sin(t * 1.2)
        glow  = int(180 + 40 * math.sin(t * 1.2))

    r = min(W, H) * 0.38 * scale
    a = min(255, glow + (60 if hovered else 0))

    gold        = (255, 200,  50, a)
    dark_gold   = (160, 100,   0, a)
    iris_fill   = ( 30,  30,  70, a)
    black_fill  = (  0,   0,   0, a)
    white_hl    = (255, 255, 255, a // 3)

    # 1. Almond eye shape (upper arc + lower arc)
    N = 64
    upper = [(cx + r * math.cos(math.pi - math.pi * i / N),
              cy - r * 0.45 * math.sin(math.pi * i / N)) for i in range(N + 1)]
    lower = [(cx + r * math.cos(math.pi - math.pi * i / N),
              cy + r * 0.38 * math.sin(math.pi * i / N)) for i in range(N, -1, -1)]
    poly = upper + lower
    d.polygon(poly, fill=(255, 210, 60, a // 4), outline=gold)

    # 2. Iris
    ir = r * 0.33
    d.ellipse([cx - ir, cy - ir, cx + ir, cy + ir], fill=iris_fill, outline=gold)

    # 3. Pupil
    pr = ir * 0.42
    d.ellipse([cx - pr, cy - pr, cx + pr, cy + pr], fill=black_fill)

    # 4. Highlight
    hr = pr * 0.28
    d.ellipse([cx - pr + hr * 0.4, cy - pr + hr * 0.4,
               cx - pr + hr * 2.4, cy - pr + hr * 2.4], fill=white_hl)

    # 5. Kohl lines (simplified Horus eye marks)
    lw = max(1, int(r * 0.07))
    # Inner corner tail downward
    x0 = int(cx - r * 0.95)
    d.line([(x0, cy), (x0 - int(r * 0.25), cy + int(r * 0.35))], fill=gold, width=lw)
    # Outer corner horizontal + curl
    x1 = int(cx + r * 0.95)
    d.line([(x1, cy), (x1 + int(r * 0.35), cy - int(r * 0.15))], fill=gold, width=lw)
    d.line([(x1 + int(r * 0.35), cy - int(r * 0.15)),
            (x1 + int(r * 0.35), cy + int(r * 0.55))], fill=gold, width=lw)

    return img


# ─── Win32 helpers ────────────────────────────────────────────────────────────

GWL_EXSTYLE       = -20
WS_EX_LAYERED     = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_NOACTIVATE  = 0x08000000
WS_EX_TOOLWINDOW  = 0x00000080

def _hwnd(title: str) -> int:
    return ctypes.windll.user32.FindWindowExW(0, 0, None, title)

def set_layered_clickthrough(hwnd: int, transparent: bool) -> None:
    ex = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    ex |= WS_EX_LAYERED | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW
    if transparent:
        ex |= WS_EX_TRANSPARENT
    else:
        ex &= ~WS_EX_TRANSPARENT
    ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex)


# ─── Overlay window ───────────────────────────────────────────────────────────

class HorusOverlay:
    W = H = 160

    def __init__(self):
        self.state     = "idle"
        self.t         = 0.0
        self.hovered   = False
        self._img_ref  = None   # keep PhotoImage alive

        self.root = tk.Tk()
        self.root.title("Horus")
        self.root.withdraw()
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.configure(bg="black")
        self.root.wm_attributes("-transparentcolor", "black")

        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x  = sw - self.W - 30
        y  = sh - self.H - 70
        self.root.geometry(f"{self.W}x{self.H}+{x}+{y}")

        self.canvas = Canvas(self.root, width=self.W, height=self.H,
                             bg="black", highlightthickness=0)
        self.canvas.pack()

        self.root.deiconify()

        # Drag state
        self._drag_ox = self._drag_oy = 0
        self._drag_moved = False
        self.canvas.bind("<ButtonPress-1>",   self._on_press)
        self.canvas.bind("<B1-Motion>",       self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)

        # Start loops
        self.root.after(150,  self._init_win32)
        self.root.after(16,   self._tick)       # ~60 fps render
        self.root.after(40,   self._poll_hover) # 25 fps hover poll

        # WebSocket listener
        threading.Thread(target=self._ws_loop, daemon=True).start()

    # ── Win32 setup ──────────────────────────────────────────────────────────

    def _init_win32(self):
        hwnd = _hwnd("Horus")
        if hwnd:
            set_layered_clickthrough(hwnd, transparent=True)

    def _set_clickthrough(self, transparent: bool):
        hwnd = _hwnd("Horus")
        if hwnd:
            set_layered_clickthrough(hwnd, transparent)

    # ── Hover polling ────────────────────────────────────────────────────────

    def _poll_hover(self):
        try:
            pt = ctypes.wintypes.POINT()
            ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
            wx = self.root.winfo_x()
            wy = self.root.winfo_y()
            over = (wx <= pt.x <= wx + self.W) and (wy <= pt.y <= wy + self.H)
            if over != self.hovered:
                self.hovered = over
                self._set_clickthrough(not over)
        except Exception:
            pass
        self.root.after(40, self._poll_hover)

    # ── Animation tick ───────────────────────────────────────────────────────

    def _tick(self):
        self.t += 0.033

        img = draw_horus_eye(self.W, self.state, self.t, self.hovered)

        if self.state == "speaking":
            alpha = 0.88 + 0.08 * math.sin(self.t * 8)
        elif self.state == "thinking":
            alpha = 0.65 + 0.10 * math.sin(self.t * 3)
        else:
            alpha = 0.15 + 0.06 * math.sin(self.t * 1.2)

        if self.hovered:
            alpha = min(0.95, alpha + 0.40)

        self.root.attributes("-alpha", round(alpha, 3))

        self._img_ref = ImageTk.PhotoImage(img)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor="nw", image=self._img_ref)

        self.root.after(16, self._tick)

    # ── Drag / click ─────────────────────────────────────────────────────────

    def _on_press(self, e):
        self._drag_ox   = e.x_root - self.root.winfo_x()
        self._drag_oy   = e.y_root - self.root.winfo_y()
        self._drag_moved = False

    def _on_drag(self, e):
        self._drag_moved = True
        nx = e.x_root - self._drag_ox
        ny = e.y_root - self._drag_oy
        self.root.geometry(f"+{nx}+{ny}")

    def _on_release(self, e):
        if not self._drag_moved:
            webbrowser.open("http://localhost:3000")

    # ── WebSocket ────────────────────────────────────────────────────────────

    def _set_state(self, state: str):
        self.state = state

    def _ws_loop(self):
        async def run():
            while True:
                try:
                    async with websockets.connect("ws://localhost:8000/ws") as ws:
                        async for raw in ws:
                            try:
                                data   = json.loads(raw)
                                status = str(data.get("status", "")).lower()
                                if "speak" in status:
                                    ns = "speaking"
                                elif "think" in status or "process" in status:
                                    ns = "thinking"
                                else:
                                    ns = "idle"
                                self.root.after(0, lambda s=ns: self._set_state(s))
                            except Exception:
                                pass
                except Exception:
                    await asyncio.sleep(3)
        asyncio.run(run())

    def run(self):
        self.root.mainloop()


# ─── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    overlay = HorusOverlay()
    overlay.run()
