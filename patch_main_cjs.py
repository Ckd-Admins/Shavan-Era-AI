file_path = r"d:\era-voice-assistant\electron\main.cjs"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

target = '''function getPythonExe() {
  const candidates = [
    path.join(PYTHON_RUNTIME_DIR, 'python.exe'),
    path.join(PYTHON_RUNTIME_DIR, 'pythonw.exe'),
    'D:\\\\era_agent\\\\.venv\\\\Scripts\\\\python.exe',
    'python',
    'python3',
  ];
  for (const c of candidates) {
    if (c === 'python' || c === 'python3') return c; // let OS resolve
    if (fs.existsSync(c)) return c;
  }
  return 'python';
}'''

replacement = '''function getPythonExe() {
  const candidates = [
    path.join(PYTHON_RUNTIME_DIR, 'python.exe'),
    path.join(PYTHON_RUNTIME_DIR, 'pythonw.exe'),
    'C:\\\\Users\\\\MSI\\\\AppData\\\\Local\\\\Programs\\\\ERA AI Assistant\\\\resources\\\\python_runtime\\\\python.exe',
    'D:\\\\era-voice-assistant\\\\resources\\\\python_runtime\\\\python.exe',
    'D:\\\\era_agent\\\\.venv\\\\Scripts\\\\python.exe',
  ];
  for (const c of candidates) {
    if (fs.existsSync(c)) {
      writeLog('info', `Resolved Python executable: ${c}`);
      return c;
    }
  }
  return 'python';
}'''

if target in content:
    content = content.replace(target, replacement)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
    print("main.cjs getPythonExe patched successfully!")
else:
    print("target not found in main.cjs")
