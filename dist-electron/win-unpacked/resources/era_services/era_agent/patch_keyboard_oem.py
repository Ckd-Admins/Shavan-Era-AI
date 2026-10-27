file_path = r"d:\era_agent\controls\keyboard.py"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

target = '''        global _cached_oem
        if _cached_oem is not None:
            return _cached_oem

        try:
            cmd = "Get-CimInstance Win32_ComputerSystem | Select-Object -ExpandProperty Manufacturer"'''

replacement = '''        global _cached_oem
        if _cached_oem is not None:
            return _cached_oem

        # 1. Fast direct Registry lookup (0ms, 100% reliable across all execution contexts)
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\\DESCRIPTION\\System\\BIOS") as key:
                m, _ = winreg.QueryValueEx(key, "SystemManufacturer")
                m_lower = str(m).strip().lower()
                if any(k in m_lower for k in ["micro-star", "msi"]):
                    _cached_oem = "msi"
                elif "lenovo" in m_lower:
                    _cached_oem = "lenovo"
                elif any(k in m_lower for k in ["asus", "asustek"]):
                    _cached_oem = "asus"
                elif any(k in m_lower for k in ["dell", "alienware"]):
                    _cached_oem = "dell"
                elif any(k in m_lower for k in ["hp", "hewlett"]):
                    _cached_oem = "hp"
                elif "acer" in m_lower:
                    _cached_oem = "acer"
                elif "samsung" in m_lower:
                    _cached_oem = "samsung"
                elif "razer" in m_lower:
                    _cached_oem = "razer"
                elif any(k in m_lower for k in ["gigabyte", "aorus"]):
                    _cached_oem = "gigabyte"
                elif any(k in m_lower for k in ["huawei", "honor", "xiaomi"]):
                    _cached_oem = "huawei"
                elif any(k in m_lower for k in ["surface", "microsoft"]):
                    _cached_oem = "surface"
                elif "toshiba" in m_lower:
                    _cached_oem = "toshiba"
                if _cached_oem:
                    return _cached_oem
        except Exception:
            pass

        try:
            cmd = "Get-CimInstance Win32_ComputerSystem | Select-Object -ExpandProperty Manufacturer"'''

if target in content:
    content = content.replace(target, replacement)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
    print("keyboard.py get_oem updated successfully!")
else:
    print("target not found in keyboard.py")
