import hid
import time
import sys

def fix_msi_keyboard(mode="rainbow", level=100):
    devs = hid.enumerate(0x1462, 0x1601)
    if not devs:
        devs = hid.enumerate(0x1462, 0)
    if not devs:
        print("ERROR: MSI Keyboard HID controller not found!")
        return False

    dev = hid.device()
    dev.open_path(devs[0]['path'])
    print("Connected to MSI Keyboard:", devs[0].get("product_string", ""))

    # Soft-reset MCU to clear single-color freeze
    reset_pkt = [0x02, 0xFF] + [0x00] * 62
    try:
        dev.send_feature_report(bytes(reset_pkt))
    except Exception:
        pass
    time.sleep(0.05)

    scale = max(0.0, min(1.0, level / 100.0))

    if mode == "off" or level == 0:
        pkt1 = [0x02, 0x01, 0x0F] + [0x00] * 61
        dev.send_feature_report(bytes(pkt1))
        time.sleep(0.02)
        pkt2 = [0x02, 0x02, 0x00, 0x58, 0x02, 0x00, 0x00, 0x0F, 0x01, 0x00, 0x00, 0, 0, 0, 0x64, 0, 0, 0] + [0x00] * 47
        dev.send_feature_report(bytes(pkt2))
        time.sleep(0.02)
    elif mode in ("rainbow", "wave"):
        pkt1 = [0x02, 0x01, 0x0F] + [0x00] * 61
        dev.send_feature_report(bytes(pkt1))
        time.sleep(0.02)
        r1, g1, b1 = int(255 * scale), 0, 0
        r2, g2, b2 = 0, int(255 * scale), 0
        r3, g3, b3 = 0, 0, int(255 * scale)
        pkt2 = [
            0x02, 0x02, 0x04, 0x2C, 0x01, 0x00, 0x00, 0x0F, 0x01, 0x01,
            0x00, r1, g1, b1,
            0x21, r2, g2, b2,
            0x42, r3, g3, b3,
            0x64, r1, g1, b1
        ]
        pkt2 += [0x00] * (64 - len(pkt2))
        dev.send_feature_report(bytes(pkt2))
        time.sleep(0.02)
    elif mode == "multicolor":
        zone_colors = [
            (1, int(255 * scale), 0, 0),
            (2, 0, int(255 * scale), 0),
            (4, 0, 0, int(255 * scale)),
            (8, int(255 * scale), int(128 * scale), int(255 * scale))
        ]
        for zone_mask, r, g, b in zone_colors:
            pkt1 = [0x02, 0x01, zone_mask] + [0x00] * 61
            dev.send_feature_report(bytes(pkt1))
            time.sleep(0.02)
            pkt2 = [0x02, 0x02, 0x01, 0x58, 0x02, 0x00, 0x00, 0x0F, 0x01, 0x00, 0x00, r, g, b, 0x64, r, g, b] + [0x00] * 47
            dev.send_feature_report(bytes(pkt2))
            time.sleep(0.02)
    else:
        val = int(255 * scale)
        pkt1 = [0x02, 0x01, 0x0F] + [0x00] * 61
        dev.send_feature_report(bytes(pkt1))
        time.sleep(0.02)
        pkt2 = [0x02, 0x02, 0x01, 0x58, 0x02, 0x00, 0x00, 0x0F, 0x01, 0x00, 0x00, val, val, val, 0x64, val, val, val] + [0x00] * 47
        dev.send_feature_report(bytes(pkt2))
        time.sleep(0.02)

    pkt3 = [0x02, 0xA0] + [0x00] * 62
    dev.send_feature_report(bytes(pkt3))
    time.sleep(0.02)
    dev.close()
    print(f"SUCCESS: Reconfigured MSI Keyboard mode={mode}, level={level}%")
    return True

if __name__ == "__main__":
    m = sys.argv[1] if len(sys.argv) > 1 else "rainbow"
    l = int(sys.argv[2]) if len(sys.argv) > 2 else 100
    fix_msi_keyboard(m, l)
