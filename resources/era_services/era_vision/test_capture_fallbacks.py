"""Test multi-tier capture fallbacks."""

import struct
import time
from PIL import Image
import mss

def capture_with_fallbacks() -> Image.Image:
    # Tier 1: mss
    try:
        with mss.mss() as sct:
            monitor = sct.monitors[0]
            shot = sct.grab(monitor)
            img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
            print("Tier 1 (mss) succeeded:", img.size)
            return img
    except Exception as exc:
        print("Tier 1 (mss) failed:", exc)

    # Tier 2: PIL ImageGrab
    try:
        from PIL import ImageGrab
        img = ImageGrab.grab()
        if img:
            print("Tier 2 (ImageGrab) succeeded:", img.size)
            return img.convert("RGB")
    except Exception as exc:
        print("Tier 2 (ImageGrab) failed:", exc)

    # Tier 3: ctypes GDI
    try:
        import ctypes
        user32 = ctypes.windll.user32
        gdi32 = ctypes.windll.gdi32
        user32.SetProcessDPIAware()
        w = user32.GetSystemMetrics(0) or 1920
        h = user32.GetSystemMetrics(1) or 1080
        
        hdcScreen = user32.GetDC(0)
        hdcMem = gdi32.CreateCompatibleDC(hdcScreen)
        hbm = gdi32.CreateCompatibleBitmap(hdcScreen, w, h)
        gdi32.SelectObject(hdcMem, hbm)
        gdi32.BitBlt(hdcMem, 0, 0, w, h, hdcScreen, 0, 0, 0x00CC0020)
        
        # Read bitmap bits
        bmpinfo = ctypes.create_string_buffer(44)
        # BGR struct
        bmpheader = struct.pack('iiihhIIIIII', 44, w, -h, 1, 32, 0, w*h*4, 0, 0, 0, 0)
        buf = ctypes.create_string_buffer(w * h * 4)
        gdi32.GetDIBits(hdcMem, hbm, 0, h, buf, bmpheader, 0)
        
        gdi32.DeleteObject(hbm)
        gdi32.DeleteDC(hdcMem)
        user32.ReleaseDC(0, hdcScreen)
        
        img = Image.frombytes("RGBA", (w, h), buf.raw).convert("RGB")
        print("Tier 3 (ctypes GDI) succeeded:", img.size)
        return img
    except Exception as exc:
        print("Tier 3 (ctypes GDI) failed:", exc)

    # Tier 4: Workspace image fallback
    import os
    ws_path = "D:\\era-voice-assistant\\workspace\\current_screen.png"
    if os.path.exists(ws_path):
        img = Image.open(ws_path).convert("RGB")
        print("Tier 4 (workspace file) succeeded:", img.size)
        return img

    raise RuntimeError("All capture tiers failed")

if __name__ == "__main__":
    try:
        img = capture_with_fallbacks()
        print("Final captured image size:", img.size)
    except Exception as e:
        print("Final result:", e)
