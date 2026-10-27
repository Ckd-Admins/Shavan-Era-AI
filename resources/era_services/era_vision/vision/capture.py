"""Screen capture.

Uses `mss` for fast, cross-platform-capable screen grabs, and Pillow for
encoding/resizing/cropping. All capture calls happen on a single dedicated
thread (`mss` instances are not thread-safe / not safe to share across
threads on Windows), via `CaptureWorker`.

On Windows, some window types (DRM-protected video, some elevated windows,
some games using exclusive fullscreen) will return black or garbage frames.
`is_probably_blank()` gives a best-effort detector for that so the rest of
the pipeline can report it rather than silently analyzing a black frame.
"""

from __future__ import annotations

import io
import logging
import queue
import threading
import time
from dataclasses import dataclass

import numpy as np
from PIL import Image

try:
    import mss
except ImportError:  # pragma: no cover - exercised only when mss truly missing
    mss = None  # type: ignore[assignment]

logger = logging.getLogger("era_vision.capture")


class CaptureError(RuntimeError):
    pass


@dataclass
class Frame:
    image: Image.Image          # RGB Pillow image, full captured frame
    width: int
    height: int
    captured_at: float

    def to_jpeg_bytes(self, quality: int = 70, max_dim: int = 1280) -> bytes:
        img = self.image
        if max(img.size) > max_dim:
            scale = max_dim / max(img.size)
            img = img.resize((max(1, int(img.width * scale)), max(1, int(img.height * scale))))
        buf = io.BytesIO()
        img.convert("RGB").save(buf, format="JPEG", quality=quality)
        return buf.getvalue()

    def crop(self, bbox: tuple[int, int, int, int]) -> "Frame":
        x0, y0, x1, y1 = bbox
        x0 = max(0, min(x0, self.width - 1))
        y0 = max(0, min(y0, self.height - 1))
        x1 = max(x0 + 1, min(x1, self.width))
        y1 = max(y0 + 1, min(y1, self.height))
        cropped = self.image.crop((x0, y0, x1, y1))
        return Frame(image=cropped, width=cropped.width, height=cropped.height, captured_at=self.captured_at)

    def to_small_grayscale_array(self, cols: int, rows: int) -> np.ndarray:
        """Downscaled grayscale array used by the change detector. Cheap and
        deliberately low-resolution -- this is not meant to be visually
        meaningful, only to detect that *something* changed."""
        small = self.image.convert("L").resize((cols, rows), Image.BILINEAR)
        return np.asarray(small, dtype=np.float32)


def is_probably_blank(frame: Frame) -> bool:
    """Heuristic for capture returning a black/near-uniform frame, which
    happens for some DRM-protected or exclusive-fullscreen windows."""
    arr = np.asarray(frame.image.convert("L"), dtype=np.uint8)
    if arr.size == 0:
        return True
    std = float(arr.std())
    mean = float(arr.mean())
    # Near-zero variance and near-zero (or near-max, e.g. pure white) mean
    # is very unlikely for a real desktop frame.
    return std < 1.5 and (mean < 5.0 or mean > 250.0)


class CaptureWorker:
    """Owns the single thread that talks to `mss`.

    All public methods are safe to call from any thread; work is dispatched
    to the capture thread via a queue and results returned through a Future-
    like mechanism (simple queue-based request/response).
    """

    def __init__(self) -> None:
        if mss is None:
            raise CaptureError(
                "The 'mss' package is not installed. Install it with "
                "'pip install mss' (see requirements.txt)."
            )
        self._req_q: "queue.Queue[tuple[str, queue.Queue]]" = queue.Queue()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="vision-capture", daemon=True)
        self._thread.start()

    def _run(self) -> None:
        try:
            sct = mss.mss() if mss else None
        except Exception as exc:  # noqa: BLE001
            logger.warning("MSS init warning, using GDI/ImageGrab fallbacks: %s", exc)
            sct = None

        while not self._stop.is_set():
            try:
                action, reply_q = self._req_q.get(timeout=0.5)
            except queue.Empty:
                continue
            if action == "stop":
                reply_q.put(None)
                break
            try:
                frame = self._grab_frame_internal(sct)
                reply_q.put(("ok", frame))
            except Exception as exc:  # noqa: BLE001 - reported to caller, not swallowed
                logger.exception("Screen capture failed across all fallbacks")
                reply_q.put(("error", exc))

    def _grab_frame_internal(self, sct: any) -> Frame:
        # Tier 1: mss
        if sct is not None:
            try:
                monitor = sct.monitors[0]
                shot = sct.grab(monitor)
                img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
                return Frame(image=img, width=img.width, height=img.height, captured_at=time.time())
            except Exception as exc:
                logger.debug("Tier 1 mss grab failed, trying fallbacks: %s", exc)

        # Tier 2: PIL ImageGrab
        try:
            from PIL import ImageGrab
            img = ImageGrab.grab()
            if img:
                img_rgb = img.convert("RGB")
                return Frame(image=img_rgb, width=img_rgb.width, height=img_rgb.height, captured_at=time.time())
        except Exception as exc:
            logger.debug("Tier 2 ImageGrab failed: %s", exc)

        # Tier 3: ctypes GDI CreateDCW
        try:
            import ctypes
            import struct
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

            bmpheader = struct.pack('iiihhIIIIII', 44, w, -h, 1, 32, 0, w * h * 4, 0, 0, 0, 0)
            buf = ctypes.create_string_buffer(w * h * 4)
            gdi32.GetDIBits(hdcMem, hbm, 0, h, buf, bmpheader, 0)

            gdi32.DeleteObject(hbm)
            gdi32.DeleteDC(hdcMem)
            user32.ReleaseDC(0, hdcScreen)

            img = Image.frombytes("RGBA", (w, h), buf.raw).convert("RGB")
            return Frame(image=img, width=img.width, height=img.height, captured_at=time.time())
        except Exception as exc:
            logger.debug("Tier 3 ctypes GDI failed: %s", exc)

        # Tier 4: Workspace image file fallback - use portable paths
        import os
        import subprocess
        _app_data = os.environ.get("ERA_APP_DATA", "")
        _ws_dir = os.environ.get("ERA_WORKSPACE_DIR", "")
        _candidates = [
            os.path.join(_ws_dir, "current_screen.png") if _ws_dir else "",
            os.path.join(_app_data, "workspace", "current_screen.png") if _app_data else "",
            os.path.join(os.environ.get("USERPROFILE", ""), "AppData", "Local", "ERA", "workspace", "current_screen.png"),
            "D:\\era-voice-assistant\\workspace\\current_screen.png",
        ]
        ws_path = next((p for p in _candidates if p and os.path.exists(p)), "")
        if ws_path and os.path.exists(ws_path):
            img = Image.open(ws_path).convert("RGB")
            return Frame(image=img, width=img.width, height=img.height, captured_at=time.time())

        # Tier 5: Direct PowerShell .NET screen grab fallback
        try:
            target_out = next((p for p in _candidates if p), "")
            if target_out:
                os.makedirs(os.path.dirname(target_out), exist_ok=True)
                esc = target_out.replace("'", "''")
                ps_cmd = f"Add-Type -AssemblyName System.Windows.Forms,System.Drawing; $b=[System.Windows.Forms.Screen]::PrimaryScreen.Bounds; $bmp=New-Object System.Drawing.Bitmap($b.Width,$b.Height); $g=[System.Drawing.Graphics]::FromImage($bmp); $g.CopyFromScreen($b.Location,[System.Drawing.Point]::Empty,$b.Size); $bmp.Save('{esc}',[System.Drawing.Imaging.ImageFormat]::Png); $g.Dispose(); $bmp.Dispose()"
                subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], timeout=4.0, capture_output=True)
                if os.path.exists(target_out):
                    img = Image.open(target_out).convert("RGB")
                    return Frame(image=img, width=img.width, height=img.height, captured_at=time.time())
        except Exception as exc:
            logger.debug("Tier 5 PowerShell screen capture failed: %s", exc)

        raise CaptureError("All screen capture tiers (mss, ImageGrab, GDI, workspace, PowerShell) failed.")

    def grab(self, timeout: float = 5.0) -> Frame:
        reply_q: "queue.Queue" = queue.Queue(maxsize=1)
        self._req_q.put(("grab", reply_q))
        try:
            result = reply_q.get(timeout=timeout)
        except queue.Empty as exc:
            raise CaptureError("Screen capture timed out") from exc
        status, payload = result
        if status == "error":
            raise CaptureError(f"Screen capture failed: {payload}") from payload
        return payload

    def close(self) -> None:
        self._stop.set()
        reply_q: "queue.Queue" = queue.Queue(maxsize=1)
        self._req_q.put(("stop", reply_q))
        try:
            reply_q.get(timeout=5.0)
        except queue.Empty:
            logger.warning("Capture worker did not acknowledge stop within 5s; thread may already be dead.")
        self._thread.join(timeout=5.0)
