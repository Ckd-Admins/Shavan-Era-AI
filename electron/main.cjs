/**
 * ERA AI Assistant - Electron Main Process
 * 
 * Manages the full ERA service lifecycle:
 *   Port 8000 - ERA Local Agent (Python FastAPI)
 *   Port 8100 - ERA Bridge Gateway (Python FastAPI / uvicorn)
 *   Port 8200 - ERA Vision Agent (Python FastAPI / uvicorn)
 *   Port 3000 - ERA Voice Assistant UI (Node.js Express)
 * 
 * Version: 1.0.0
 */
'use strict';

const { app, BrowserWindow, Tray, Menu, ipcMain, shell, nativeImage, dialog } = require('electron');
const path = require('path');
const fs = require('fs');
const { spawn, exec } = require('child_process');
const http = require('http');
const os = require('os');

// ─── Global error handlers ───────────────────────────────────────────────────
process.on('uncaughtException', (error) => {
  writeLog('error', `[Main] Uncaught exception: ${error.stack || error.message}`);
  console.error('[ERA Main] uncaughtException:', error);
});
process.on('unhandledRejection', (reason) => {
  writeLog('error', `[Main] Unhandled rejection: ${reason}`);
  console.error('[ERA Main] unhandledRejection:', reason);
});

// ─── Version / Build info ────────────────────────────────────────────────────
const ERA_VERSION = '1.0.0';
const APP_ID = 'com.era.assistant';

// ─── Mode flags ──────────────────────────────────────────────────────────────
const isDev = !app.isPackaged || process.env.NODE_ENV === 'development' || process.argv.includes('--dev');
const isDebug = process.argv.includes('--debug');

// ─── Single Instance Lock ─────────────────────────────────────────────────────
const gotLock = app.requestSingleInstanceLock();
if (!gotLock) {
  // Another instance already running — focus it
  app.quit();
  process.exit(0);
}
app.on('second-instance', () => {
  if (mainWindow) {
    if (mainWindow.isMinimized()) mainWindow.restore();
    mainWindow.show();
    mainWindow.focus();
  }
});

// ─── Directory resolution ─────────────────────────────────────────────────────
const APP_DIR = path.resolve(__dirname, '..');

function getResourcesDir() {
  if (app.isPackaged) {
    return process.resourcesPath;
  }
  return APP_DIR;
}

const RESOURCES_DIR = getResourcesDir();
const ERA_SERVICES_DIR = path.join(RESOURCES_DIR, 'era_services');
const PYTHON_RUNTIME_DIR = path.join(RESOURCES_DIR, 'python_runtime');

// Python executable: prefer bundled runtime, fallback to system Python
function getPythonExe() {
  const candidates = [
    path.join(PYTHON_RUNTIME_DIR, 'python.exe'),
    path.join(PYTHON_RUNTIME_DIR, 'pythonw.exe'),
    'C:\\Users\\MSI\\AppData\\Local\\Programs\\ERA AI Assistant\\resources\\python_runtime\\python.exe',
    'D:\\era-voice-assistant\\resources\\python_runtime\\python.exe',
    'D:\\era_agent\\.venv\\Scripts\\python.exe',
  ];
  for (const c of candidates) {
    if (fs.existsSync(c)) {
      // Resolved python
      return c;
    }
  }
  return 'python';
}

const PYTHON_EXE = getPythonExe();

// Agent/service source directories
function getServiceDir(name) {
  // Try packaged resources first
  const packed = path.join(ERA_SERVICES_DIR, name);
  if (fs.existsSync(packed)) return packed;
  // Dev fallbacks
  const devPaths = {
    era_agent: 'D:\\era_agent',
    era_bridge: 'D:\\era_bridge\\era_bridge',
    era_vision: 'D:\\era_vision\\era_vision_agent_phase2\\era_vision_agent',
  };
  return devPaths[name] || packed;
}

// ─── User App Data ─────────────────────────────────────────────────────────────
// All mutable ERA user data goes here — NOT inside the install dir
const ERA_APP_DATA = path.join(os.homedir(), 'AppData', 'Local', 'ERA');
const ERA_LOGS_DIR  = path.join(ERA_APP_DATA, 'logs');
const ERA_CONFIG_DIR = path.join(ERA_APP_DATA, 'config');
const ERA_WORKSPACE_DIR = path.join(ERA_APP_DATA, 'workspace');
const ERA_FIRST_RUN_FLAG = path.join(ERA_APP_DATA, '.first_run_complete');

// Ensure directories exist
for (const dir of [ERA_LOGS_DIR, ERA_CONFIG_DIR, ERA_WORKSPACE_DIR]) {
  fs.mkdirSync(dir, { recursive: true });
}

// ─── ERA Central URL resolution ───────────────────────────────────────────────
// Priority: process.env.ERA_CENTRAL_URL > user AppData config > bundled template
// An empty/missing value means telemetry is disabled — this is the safe default.
function getEraCentralUrl() {
  // 1. Explicit environment variable (CI / packaged launcher override)
  if (process.env.ERA_CENTRAL_URL && process.env.ERA_CENTRAL_URL.trim()) {
    return process.env.ERA_CENTRAL_URL.trim();
  }
  // 2. User-editable config in AppData (survives upgrades)
  const userCfgPath = path.join(ERA_CONFIG_DIR, 'era_production.json');
  // 3. Bundled read-only template (ships with installer, empty by default)
  const bundledCfgPath = path.join(APP_DIR, 'config', 'era_production.json');
  for (const cfgPath of [userCfgPath, bundledCfgPath]) {
    try {
      if (fs.existsSync(cfgPath)) {
        const cfg = JSON.parse(fs.readFileSync(cfgPath, 'utf8'));
        if (cfg && typeof cfg.centralUrl === 'string' && cfg.centralUrl.trim()) {
          return cfg.centralUrl.trim();
        }
      }
    } catch { /* ignore parse errors — disabled is safe */ }
  }
  return ''; // disabled
}

// ─── Logging ──────────────────────────────────────────────────────────────────
const LOG_FILES = {
  launcher: path.join(ERA_LOGS_DIR, 'launcher.log'),
  error:    path.join(ERA_LOGS_DIR, 'error.log'),
};

function writeLog(level, message) {
  const ts = new Date().toISOString();
  const line = `[${ts}] [${level.toUpperCase()}] ${message}\n`;
  const target = level === 'error' ? LOG_FILES.error : LOG_FILES.launcher;
  try { fs.appendFileSync(target, line); } catch {}
  if (isDebug) console.log(line.trim());
}

writeLog('info', `ERA v${ERA_VERSION} launcher starting. isPackaged=${app.isPackaged} isDev=${isDev}`);
writeLog('info', `RESOURCES_DIR: ${RESOURCES_DIR}`);
writeLog('info', `ERA_APP_DATA:  ${ERA_APP_DATA}`);
writeLog('info', `PYTHON_EXE:    ${PYTHON_EXE}`);

// Resolve ERA Central URL once at startup (read-only thereafter)
const ERA_CENTRAL_URL = getEraCentralUrl();
writeLog('info', `ERA_CENTRAL_URL: ${ERA_CENTRAL_URL || '(not configured — telemetry disabled)'}`);

// ─── Global state ─────────────────────────────────────────────────────────────
let mainWindow   = null;
let tray         = null;
let splashWindow = null;
let isShuttingDown = false;

const childProcesses = {
  agent:  null,  // port 8000
  bridge: null,  // port 8100
  vision: null,  // port 8200
  server: null,  // port 3000 (express) — started via require()
};

const PORTS = {
  agent:  8000,
  bridge: 8100,
  vision: 8200,
  server: 3000,
};

const HEALTH_URLS = {
  agent:  `http://127.0.0.1:${PORTS.agent}/status`,
  bridge: `http://127.0.0.1:${PORTS.bridge}/v1/status`,
  vision: `http://127.0.0.1:${PORTS.vision}/v1/health`,
  server: `http://127.0.0.1:${PORTS.server}/api/health`,
};

// ─── Port utilities ───────────────────────────────────────────────────────────
function isPortBusy(port) {
  return new Promise((resolve) => {
    const req = http.get(`http://127.0.0.1:${port}/`, { timeout: 800 }, () => resolve(true));
    req.on('error', () => resolve(false));
    req.on('timeout', () => { req.destroy(); resolve(false); });
    req.end();
  });
}

function waitForUrl(url, timeoutMs = 60000, intervalMs = 1000) {
  return new Promise((resolve) => {
    const deadline = Date.now() + timeoutMs;
    const check = () => {
      const req = http.get(url, { timeout: 2000 }, (res) => {
        if (res.statusCode < 500) { resolve(true); return; }
        scheduleRetry();
      });
      req.on('error', scheduleRetry);
      req.on('timeout', () => { req.destroy(); scheduleRetry(); });
      req.end();
    };
    function scheduleRetry() {
      if (Date.now() >= deadline) { resolve(false); return; }
      setTimeout(check, intervalMs);
    }
    check();
  });
}

// ─── Kill stale processes on ports ────────────────────────────────────────────
function killProcessOnPort(port) {
  return new Promise((resolve) => {
    exec(`for /f "tokens=5" %A in ('netstat -ano ^| findstr ":${port} "') do taskkill /PID %A /F`, (err) => {
      resolve();
    });
  });
}

async function cleanupStalePorts() {
  writeLog('info', 'Cleaning up stale processes on ERA ports...');
  const kills = Object.values(PORTS).map(p => killProcessOnPort(p));
  await Promise.all(kills);
  await new Promise(r => setTimeout(r, 1500));
  writeLog('info', 'Port cleanup complete.');
}

// ─── Env construction for Python services ────────────────────────────────────
function buildEnvForService(serviceDir, extraEnv = {}) {
  const env = {
    ...process.env,
    ERA_APP_DATA,
    ERA_CONFIG_DIR,
    ERA_WORKSPACE_DIR,
    PYTHONDONTWRITEBYTECODE: '1',
    PYTHONUNBUFFERED: '1',
    // Tell the Python agent it is running inside an Electron EXE so it can
    // choose the correct app-launch strategy (PowerShell-first instead of
    // os.startfile-first, which fails in the Electron child-process context).
    ERA_RUNNING_IN_ELECTRON: '1',
    ...extraEnv,
  };

  // Strip ALL Electron/Node-specific variables so Python child-processes can
  // freely launch GUI apps (VS Code, Spotify, Chrome, etc.) without being
  // blocked by UIPI or triggering "access denied" errors that cause Windows beep sounds.
  for (const k of Object.keys(env)) {
    const ku = k.toUpperCase();
    if (
      ku.startsWith('ELECTRON_') ||
      ku.startsWith('NODE_') ||
      ku === 'NODE_OPTIONS' ||
      ku === 'NODE_PATH' ||
      ku === 'CHROME_EXTRA_FLAGS'
    ) {
      delete env[k];
    }
  }

  // Make sure bundled Python packages and SSL certs are discoverable
  if (fs.existsSync(PYTHON_RUNTIME_DIR)) {
    const sitePackages = path.join(PYTHON_RUNTIME_DIR, 'Lib', 'site-packages');
    const existing = env.PYTHONPATH || '';
    env.PYTHONPATH = sitePackages + (existing ? path.delimiter + existing : '');

    const caCert = path.join(sitePackages, 'certifi', 'cacert.pem');
    if (fs.existsSync(caCert)) {
      env.REQUESTS_CA_BUNDLE = caCert;
      env.SSL_CERT_FILE = caCert;
    }
  }
  return env;
}

// ─── Service launchers ────────────────────────────────────────────────────────

function startAgentService() {
  const serviceDir = getServiceDir('era_agent');
  writeLog('info', `Starting ERA Local Agent from: ${serviceDir}`);

  // Write minimal .env for agent
  const agentEnvPath = path.join(serviceDir, '.env');
  if (!fs.existsSync(agentEnvPath)) {
    const credPath = path.join(serviceDir, 'credentials.json');
    const tokenPath = path.join(serviceDir, 'token.json');
    const envContent = [
      `GMAIL_CREDENTIALS_PATH=${credPath}`,
      `GMAIL_TOKEN_PATH=${tokenPath}`,
      `ERA_HOST=127.0.0.1`,
      `ERA_PORT=8000`,
      `WORKSPACE_DIR=${ERA_WORKSPACE_DIR}`,
      `ERA_AGENT_API_KEY=era_internal_local_agent_key`,
    ].join('\n');
    try { fs.writeFileSync(agentEnvPath, envContent); } catch {}
  }

  const env = buildEnvForService(serviceDir, {
    ERA_HOST: '127.0.0.1',
    ERA_PORT: '8000',
    WORKSPACE_DIR: ERA_WORKSPACE_DIR,
    ERA_AGENT_API_KEY: 'era_internal_local_agent_key',
  });

  const logFile = path.join(ERA_LOGS_DIR, 'agent.log');
  const logStream = fs.createWriteStream(logFile, { flags: 'a' });

  const proc = spawn(PYTHON_EXE, ['-m', 'uvicorn', 'api_server:app', '--host', '127.0.0.1', '--port', '8000', '--log-level', 'warning'], {
    cwd: serviceDir,
    env,
    stdio: ['ignore', 'pipe', 'pipe'],
    windowsHide: true,
  });

  proc.stdout.on('data', d => logStream.write(`[AGENT] ${d}`));
  proc.stderr.on('data', d => logStream.write(`[AGENT-ERR] ${d}`));
  proc.on('error', err => writeLog('error', `Agent process error: ${err.message}`));
  proc.on('exit', (code, sig) => {
    writeLog('warn', `Agent exited: code=${code} signal=${sig}`);
    if (!isShuttingDown) {
      writeLog('info', 'Restarting agent in 5s...');
      setTimeout(startAgentService, 5000);
    }
  });

  childProcesses.agent = proc;
  writeLog('info', `Agent process PID: ${proc.pid}`);
}

function startBridgeService() {
  const serviceDir = getServiceDir('era_bridge');
  writeLog('info', `Starting ERA Bridge from: ${serviceDir}`);

  // Write .env for bridge with runtime-resolved agent dir
  const bridgeEnvPath = path.join(serviceDir, '.env');
  const agentDir = getServiceDir('era_agent');
  const envLines = [
    `AGENT_PROJECT_DIR=${agentDir}`,
    `AGENT_START_COMMAND=python api_server.py`,
    `AGENT_AUTOSTART_ON_BRIDGE_BOOT=false`,
    `BRIDGE_HOST=127.0.0.1`,
    `BRIDGE_PORT=8100`,
    `BRIDGE_API_KEY=era_bridge_secret_key_2026`,
    `VISION_AGENT_URL=http://127.0.0.1:8200`,
    `VISION_AGENT_API_KEY=era_vision_secret_key_2026`,
  ];
  // Only set ERA_CENTRAL_URL when configured — empty value disables telemetry in Bridge
  if (ERA_CENTRAL_URL) {
    envLines.push(`ERA_CENTRAL_URL=${ERA_CENTRAL_URL}`);
  }
  try { fs.writeFileSync(bridgeEnvPath, envLines.join('\n')); } catch {}

  const spawnEnvExtra = {
    BRIDGE_HOST: '127.0.0.1',
    BRIDGE_PORT: '8100',
    BRIDGE_API_KEY: 'era_bridge_secret_key_2026',
    VISION_AGENT_URL: 'http://127.0.0.1:8200',
    VISION_AGENT_API_KEY: 'era_vision_secret_key_2026',
    ERA_AGENT_API_KEY: 'era_internal_local_agent_key',
  };
  if (ERA_CENTRAL_URL) {
    spawnEnvExtra.ERA_CENTRAL_URL = ERA_CENTRAL_URL;
  }
  const env = buildEnvForService(serviceDir, spawnEnvExtra);

  const logFile = path.join(ERA_LOGS_DIR, 'bridge.log');
  const logStream = fs.createWriteStream(logFile, { flags: 'a' });

  const proc = spawn(PYTHON_EXE, ['main.py'], {
    cwd: serviceDir,
    env,
    stdio: ['ignore', 'pipe', 'pipe'],
    windowsHide: true,
  });

  proc.stdout.on('data', d => logStream.write(`[BRIDGE] ${d}`));
  proc.stderr.on('data', d => logStream.write(`[BRIDGE-ERR] ${d}`));
  proc.on('error', err => writeLog('error', `Bridge process error: ${err.message}`));
  proc.on('exit', (code, sig) => {
    writeLog('warn', `Bridge exited: code=${code} signal=${sig}`);
    if (!isShuttingDown) {
      writeLog('info', 'Restarting bridge in 5s...');
      setTimeout(startBridgeService, 5000);
    }
  });

  childProcesses.bridge = proc;
  writeLog('info', `Bridge process PID: ${proc.pid}`);
}

function startVisionService() {
  const serviceDir = getServiceDir('era_vision');
  writeLog('info', `Starting ERA Vision Agent from: ${serviceDir}`);

  // Helper to read decrypted Gemini key from AppData keys.enc
  function getSavedGeminiKey() {
    try {
      const encPath = path.join(ERA_CONFIG_DIR, 'keys.enc');
      if (!fs.existsSync(encPath)) return '';
      const crypto = require('crypto');
      const enc = fs.readFileSync(encPath, 'utf8');
      const parts = enc.split(':');
      const iv = Buffer.from(parts.shift() || '', 'hex');
      const text = Buffer.from(parts.join(':'), 'hex');
      const key = crypto.scryptSync('era-companion-agent-secret-pass', 'era-salt', 32);
      const decipher = crypto.createDecipheriv('aes-256-cbc', key, iv);
      let dec = decipher.update(text);
      dec = Buffer.concat([dec, decipher.final()]);
      const parsed = JSON.parse(dec.toString());
      return parsed.geminiApiKey || '';
    } catch {
      return '';
    }
  }

  // Read existing vision .env for API key
  const visionEnvSrc = path.join(serviceDir, '.env');
  const existingEnv = {};
  if (fs.existsSync(visionEnvSrc)) {
    const lines = fs.readFileSync(visionEnvSrc, 'utf8').split('\n');
    for (const l of lines) {
      const [k, ...rest] = l.split('=');
      if (k && k.trim() && !k.trim().startsWith('#')) {
        existingEnv[k.trim()] = rest.join('=').trim();
      }
    }
  }

  // Copy vision .env to app data if it has keys but app data doesn't
  const visionEnvDest = path.join(ERA_CONFIG_DIR, 'vision.env');
  if (!fs.existsSync(visionEnvDest) && fs.existsSync(visionEnvSrc)) {
    try { fs.copyFileSync(visionEnvSrc, visionEnvDest); } catch {}
  }

  const savedGeminiKey = getSavedGeminiKey();
  const geminiApiKey = existingEnv['GEMINI_API_KEY'] || process.env.GEMINI_API_KEY || savedGeminiKey || '';

  const env = buildEnvForService(serviceDir, {
    VISION_AGENT_HOST: '127.0.0.1',
    VISION_AGENT_PORT: '8200',
    VISION_AGENT_API_KEY: existingEnv['VISION_AGENT_API_KEY'] || 'era_vision_secret_key_2026',
    GEMINI_API_KEY: geminiApiKey,
    ERA_BRIDGE_URL: 'http://127.0.0.1:8100',
    ERA_BRIDGE_API_KEY: 'era_bridge_secret_key_2026',
    ALLOWED_ORIGINS: 'http://127.0.0.1:8100,http://localhost:8100,http://127.0.0.1:3000,http://localhost:3000',
    LOG_LEVEL: 'WARNING',
  });

  const logFile = path.join(ERA_LOGS_DIR, 'vision.log');
  const logStream = fs.createWriteStream(logFile, { flags: 'a' });

  const proc = spawn(PYTHON_EXE, ['main.py'], {
    cwd: serviceDir,
    env,
    stdio: ['ignore', 'pipe', 'pipe'],
    windowsHide: true,
  });

  proc.stdout.on('data', d => logStream.write(`[VISION] ${d}`));
  proc.stderr.on('data', d => logStream.write(`[VISION-ERR] ${d}`));
  proc.on('error', err => writeLog('error', `Vision process error: ${err.message}`));
  proc.on('exit', (code, sig) => {
    writeLog('warn', `Vision exited: code=${code} signal=${sig}`);
    if (!isShuttingDown) {
      writeLog('info', 'Restarting vision in 10s...');
      setTimeout(startVisionService, 10000);
    }
  });

  childProcesses.vision = proc;
  writeLog('info', `Vision process PID: ${proc.pid}`);
}

function startExpressServer() {
  writeLog('info', 'Starting ERA Express/WebSocket server (port 3000)...');
  const bundlePath = path.join(APP_DIR, 'dist', 'server.cjs');
  const logFile = path.join(ERA_LOGS_DIR, 'server.log');

  if (fs.existsSync(bundlePath)) {
    // Set env for the express server
    process.env.NODE_ENV       = 'production';
    process.env.ERA_APP_DATA   = ERA_APP_DATA;
    process.env.ERA_CONFIG_DIR = ERA_CONFIG_DIR;
    process.env.ERA_WORKSPACE_DIR = ERA_WORKSPACE_DIR;
    process.env.ERA_DIST_DIR   = path.join(APP_DIR, 'dist');
    try {
      require(bundlePath);
      writeLog('info', 'Express server bundle loaded in-process.');
    } catch (err) {
      writeLog('error', `Failed to load Express server bundle: ${err.message}`);
    }
  } else {
    // Dev mode: spawn tsx
    writeLog('info', 'Express bundle not found. Spawning dev tsx server...');
    const logStream = fs.createWriteStream(logFile, { flags: 'a' });
    const proc = spawn('npx', ['tsx', 'server.ts'], {
      cwd: APP_DIR,
      env: { ...process.env, ERA_APP_DATA, ERA_CONFIG_DIR, ERA_WORKSPACE_DIR },
      stdio: ['ignore', 'pipe', 'pipe'],
      shell: true,
      windowsHide: true,
    });
    proc.stdout.on('data', d => logStream.write(`[SERVER] ${d}`));
    proc.stderr.on('data', d => logStream.write(`[SERVER-ERR] ${d}`));
    proc.on('error', err => writeLog('error', `Express server error: ${err.message}`));
    childProcesses.server = proc;
    writeLog('info', `Express dev server PID: ${proc.pid}`);
  }
}

// ─── Startup splash ───────────────────────────────────────────────────────────
function createSplashWindow() {
  const iconPath = path.join(APP_DIR, 'assets', 'icon.png');
  splashWindow = new BrowserWindow({
    width: 480,
    height: 300,
    frame: false,
    transparent: false,
    resizable: false,
    center: true,
    alwaysOnTop: true,
    skipTaskbar: true,
    icon: fs.existsSync(iconPath) ? iconPath : undefined,
    webPreferences: { nodeIntegration: false, contextIsolation: true },
  });
  // Inline HTML splash
  const html = `<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><style>
  body { margin:0; background:#0a0a12; display:flex; flex-direction:column;
         align-items:center; justify-content:center; height:100vh;
         font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif; color:#fff; }
  img  { width:80px; height:80px; margin-bottom:20px; border-radius:16px; }
  h2   { margin:0 0 8px; font-size:22px; color:#60a5fa; }
  p    { margin:0 0 24px; font-size:13px; color:#94a3b8; }
  .bar { width:320px; height:4px; background:#1e293b; border-radius:4px; overflow:hidden; }
  .fill{ height:100%; background:linear-gradient(90deg,#3b82f6,#8b5cf6); animation:pulse 1.5s ease-in-out infinite; }
  @keyframes pulse { 0%,100%{opacity:.7} 50%{opacity:1} }
  .status { margin-top:12px; font-size:11px; color:#64748b; }
</style></head>
<body>
  <h2>ERA AI</h2>
  <p>Starting services…</p>
  <div class="bar"><div class="fill"></div></div>
  <div class="status" id="s">Initializing…</div>
  <script>
    const msgs = ['Starting ERA Local Agent…','Starting ERA Bridge…','Starting ERA Vision Agent…','Starting UI server…','Performing health checks…','Almost ready…'];
    let i=0; setInterval(()=>{ document.getElementById('s').textContent=msgs[i%msgs.length]; i++; },2000);
  </script>
</body></html>`;
  splashWindow.loadURL('data:text/html;charset=utf-8,' + encodeURIComponent(html));
}

// ─── Main Window ──────────────────────────────────────────────────────────────
function createMainWindow() {
  const icoPath = path.join(APP_DIR, 'assets', 'icon.ico');
  const pngPath = path.join(APP_DIR, 'assets', 'icon.png');

  mainWindow = new BrowserWindow({
    width: 1280,
    height: 820,
    minWidth: 900,
    minHeight: 600,
    title: `ERA AI Assistant v${ERA_VERSION}`,
    icon: fs.existsSync(icoPath) ? icoPath : (fs.existsSync(pngPath) ? pngPath : undefined),
    frame: true,
    show: false,
    webPreferences: {
      preload: path.join(__dirname, 'preload.cjs'),
      nodeIntegration: false,
      contextIsolation: true,
      webSecurity: false,
    },
  });

  mainWindow.setMenuBarVisibility(false);

  const MAX_RETRIES = 60;
  let retries = 0;
  function tryLoad() {
    const req = http.get(`http://localhost:${PORTS.server}/api/health`, (res) => {
      writeLog('info', 'Express health OK — loading UI.');
      mainWindow.loadURL(`http://localhost:${PORTS.server}`);
    });
    req.on('error', () => {
      if (retries++ < MAX_RETRIES) {
        setTimeout(tryLoad, 1000);
      } else {
        writeLog('error', 'Max retries hit — forcing UI load anyway.');
        mainWindow.loadURL(`http://localhost:${PORTS.server}`);
      }
    });
    req.end();
  }
  tryLoad();

  mainWindow.once('ready-to-show', () => {
    if (splashWindow && !splashWindow.isDestroyed()) {
      splashWindow.close();
      splashWindow = null;
    }
    mainWindow.show();
    mainWindow.focus();
    writeLog('info', 'ERA main window shown.');
  });

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: 'deny' };
  });

  mainWindow.on('closed', () => { mainWindow = null; });
}

// ─── System Tray ──────────────────────────────────────────────────────────────
function createSystemTray() {
  try {
    const pngPath = path.join(APP_DIR, 'assets', 'icon.png');
    if (!fs.existsSync(pngPath)) return;
    const icon = nativeImage.createFromPath(pngPath).resize({ width: 16, height: 16 });
    tray = new Tray(icon);

    const show = () => {
      if (mainWindow) {
        if (mainWindow.isMinimized()) mainWindow.restore();
        mainWindow.show();
        mainWindow.focus();
      } else {
        createMainWindow();
      }
    };

    const ctxMenu = Menu.buildFromTemplate([
      { label: `ERA AI Assistant v${ERA_VERSION}`, enabled: false },
      { type: 'separator' },
      { label: 'Open ERA', click: show },
      { label: 'Agent Status (8000)', click: () => shell.openExternal('http://127.0.0.1:8000/status') },
      { label: 'Bridge Status (8100)', click: () => shell.openExternal('http://127.0.0.1:8100/health') },
      { label: 'Vision Status (8200)', click: () => shell.openExternal('http://127.0.0.1:8200/v1/vision/status') },
      { type: 'separator' },
      { label: 'View Logs Folder', click: () => shell.openPath(ERA_LOGS_DIR) },
      { type: 'separator' },
      { label: 'Quit ERA', click: () => { cleanupAndQuit(); } },
    ]);

    tray.setToolTip(`ERA AI Assistant v${ERA_VERSION}`);
    tray.setContextMenu(ctxMenu);
    tray.on('double-click', show);
  } catch (e) {
    writeLog('error', `Could not create tray: ${e.message}`);
  }
}

// ─── Graceful Shutdown ────────────────────────────────────────────────────────
function stopChildProcess(proc, name) {
  if (!proc || !proc.pid) return;
  try {
    writeLog('info', `Stopping ${name} (PID ${proc.pid})...`);
    if (process.platform === 'win32') {
      exec(`taskkill /pid ${proc.pid} /T /F`, () => {});
    } else {
      proc.kill('SIGTERM');
    }
  } catch (e) {
    writeLog('error', `Error stopping ${name}: ${e.message}`);
  }
}

function cleanupAndQuit() {
  if (isShuttingDown) return;
  isShuttingDown = true;
  writeLog('info', 'ERA shutdown initiated.');

  stopChildProcess(childProcesses.vision, 'Vision Agent');
  stopChildProcess(childProcesses.bridge, 'Bridge Gateway');
  stopChildProcess(childProcesses.agent, 'Local Agent');
  stopChildProcess(childProcesses.server, 'Express Server');

  // Kill any remaining processes on ERA ports
  for (const port of Object.values(PORTS)) {
    exec(`for /f "tokens=5" %A in ('netstat -ano ^| findstr ":${port} "') do taskkill /PID %A /F`, () => {});
  }

  setTimeout(() => { app.quit(); }, 2000);
}

// ─── First-run detection ──────────────────────────────────────────────────────
function isFirstRun() {
  return !fs.existsSync(ERA_FIRST_RUN_FLAG);
}

function markFirstRunComplete() {
  try {
    fs.writeFileSync(ERA_FIRST_RUN_FLAG, new Date().toISOString(), 'utf8');
  } catch {}
}

function checkFirstRunRequirements() {
  const missing = [];

  // Check Python
  try {
    const result = require('child_process').spawnSync(PYTHON_EXE, ['--version'], { timeout: 5000 });
    if (result.status !== 0) missing.push('Python runtime not found');
  } catch {
    missing.push('Python runtime not accessible');
  }

  return missing;
}

// ─── IPC Handlers ────────────────────────────────────────────────────────────
ipcMain.on('open-external', (event, url) => shell.openExternal(url));
ipcMain.on('window-minimize', () => mainWindow && mainWindow.minimize());
ipcMain.on('window-maximize', () => {
  if (!mainWindow) return;
  mainWindow.isMaximized() ? mainWindow.unmaximize() : mainWindow.maximize();
});
ipcMain.on('window-close', () => mainWindow && mainWindow.close());
ipcMain.handle('get-era-info', () => ({
  version: ERA_VERSION,
  logsDir: ERA_LOGS_DIR,
  configDir: ERA_CONFIG_DIR,
  appData: ERA_APP_DATA,
  isDev,
  isDebug,
}));
ipcMain.handle('get-service-status', async () => {
  const results = {};
  for (const [name, url] of Object.entries(HEALTH_URLS)) {
    results[name] = await new Promise(resolve => {
      const req = http.get(url, { timeout: 1500 }, res => resolve(res.statusCode < 500));
      req.on('error', () => resolve(false));
      req.on('timeout', () => { req.destroy(); resolve(false); });
      req.end();
    });
  }
  return results;
});

// ─── App lifecycle ────────────────────────────────────────────────────────────
app.whenReady().then(async () => {
  writeLog('info', 'Electron app ready. Starting ERA services...');

  // Show splash immediately
  createSplashWindow();

  // First-run check
  if (isFirstRun()) {
    writeLog('info', 'First run detected — initializing ERA environment.');
    const issues = checkFirstRunRequirements();
    if (issues.length > 0) {
      const msg = `ERA Setup Issue:\n\n${issues.join('\n')}\n\nPlease ensure ERA was installed correctly.\n\nLogs: ${ERA_LOGS_DIR}`;
      dialog.showErrorBox('ERA Setup Problem', msg);
      writeLog('error', `First run issues: ${issues.join(', ')}`);
      app.quit();
      return;
    }
    markFirstRunComplete();
    writeLog('info', 'First run initialization complete.');
  }

  // Copy user config files to app data if not already there
  const agentConfigSrc = path.join(getServiceDir('era_agent'), 'config');
  const configDest = ERA_CONFIG_DIR;
  if (fs.existsSync(agentConfigSrc)) {
    try {
      const items = fs.readdirSync(agentConfigSrc);
      for (const f of items) {
        const dest = path.join(configDest, f);
        if (!fs.existsSync(dest)) {
          fs.copyFileSync(path.join(agentConfigSrc, f), dest);
          writeLog('info', `Copied config: ${f}`);
        }
      }
    } catch {}
  }

  // Copy ERA voice assistant config files (whatsapp contacts etc.)
  const voiceConfigSrc = path.join(APP_DIR, 'config');
  if (fs.existsSync(voiceConfigSrc)) {
    try {
      const items = fs.readdirSync(voiceConfigSrc);
      for (const f of items) {
        const dest = path.join(configDest, f);
        if (!fs.existsSync(dest)) {
          fs.copyFileSync(path.join(voiceConfigSrc, f), dest);
        }
      }
    } catch {}
  }

  // Kill stale port processes before startup
  await cleanupStalePorts();

  // Start services in dependency order
  writeLog('info', 'Step 1/4: Starting ERA Local Agent (port 8000)...');
  startAgentService();

  // Wait for agent before bridge
  const agentReady = await waitForUrl(HEALTH_URLS.agent, 30000);
  writeLog(agentReady ? 'info' : 'warn', `Agent ready: ${agentReady}`);

  writeLog('info', 'Step 2/4: Starting ERA Bridge (port 8100)...');
  startBridgeService();

  writeLog('info', 'Step 3/4: Starting ERA Vision Agent (port 8200)...');
  startVisionService();

  writeLog('info', 'Step 4/4: Starting ERA Express/WebSocket server (port 3000)...');
  startExpressServer();

  // Create main window (it will poll until server is ready)
  createMainWindow();
  createSystemTray();

  // Health summary after startup
  const bridgeReady  = await waitForUrl(HEALTH_URLS.bridge, 25000);
  const visionReady  = await waitForUrl(HEALTH_URLS.vision, 25000);
  const serverReady  = await waitForUrl(HEALTH_URLS.server, 60000);

  writeLog('info', `Health summary — Agent:${agentReady} Bridge:${bridgeReady} Vision:${visionReady} Server:${serverReady}`);

  if (!serverReady) {
    dialog.showErrorBox('ERA Startup Problem',
      `The ERA UI server (port 3000) did not start in time.\n\nCheck logs: ${ERA_LOGS_DIR}`);
  }

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createMainWindow();
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    cleanupAndQuit();
  }
});

app.on('will-quit', (event) => {
  if (!isShuttingDown) {
    event.preventDefault();
    cleanupAndQuit();
  }
});

app.on('before-quit', () => {
  isShuttingDown = true;
});
