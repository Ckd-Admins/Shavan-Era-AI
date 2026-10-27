import time
import requests
import base64
import io
from PIL import ImageGrab

# Change this to your deployed app URL if running remotely
APP_URL = "http://localhost:3000"
UPLOAD_URL = f"{APP_URL}/api/screen/upload"

print("📡 Continuous Real-Time Screen Feed Active -> Era Visual Persistence Engine")
print(f"📡 Target Endpoint: {UPLOAD_URL} (10 FPS Real-Time Stream)")
print("Press Ctrl+C to stop.")

req_session = requests.Session()

while True:
    try:
        start_time = time.time()
        # Capture physical desktop screen
        img = ImageGrab.grab()
        # Resize to maintain high performance and responsive streaming
        img.thumbnail((1280, 720))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=60)
        img_str = base64.b64encode(buf.getvalue()).decode('utf-8')
        
        req_session.post(UPLOAD_URL, json={"image": f"data:image/jpeg;base64,{img_str}", "mimeType": "image/jpeg"}, timeout=1.0)
        print("✅ Live video feed streaming active to Era (10 FPS).", end="\r")
        
        elapsed = time.time() - start_time
        sleep_time = max(0.01, 0.09 - elapsed)
        time.sleep(sleep_time)
    except Exception as e:
        print(f"❌ Feed Sync Error: {e}", end="\r")
        time.sleep(0.2)
