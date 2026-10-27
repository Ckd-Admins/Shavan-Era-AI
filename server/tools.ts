import fs from "fs";
import path from "path";
import { exec } from "child_process";
import { GoogleGenAI } from "@google/genai";
import { loadKeys } from "./keys";
import { executeAgentCommand } from "./agentBridge";

const WORKSPACE_DIR = process.env.ERA_WORKSPACE_DIR || path.join(process.env.LOCALAPPDATA || process.env.USERPROFILE || process.cwd(), "ERA", "workspace");
const CONFIG_DIR = process.env.ERA_CONFIG_DIR || path.join(process.env.LOCALAPPDATA || process.env.USERPROFILE || process.cwd(), "ERA", "config");

// Ensure workspace and config directories exist
for (const dir of [WORKSPACE_DIR, CONFIG_DIR]) {
  if (!fs.existsSync(dir)) {
    try { fs.mkdirSync(dir, { recursive: true }); } catch {}
  }
}

export interface ToolResult {
  success: boolean;
  message: string;
  output?: string;
  data?: any;
}

// 1. Write Code to Workspace
export function writeCode(language: string, filename: string, code: string): ToolResult {
  try {
    // Sanitize filename to prevent directory traversal
    const safeFilename = path.basename(filename);
    const filePath = path.join(WORKSPACE_DIR, safeFilename);
    
    fs.writeFileSync(filePath, code, "utf8");
    return {
      success: true,
      message: `Successfully wrote ${language} code to ${safeFilename}`,
      data: { filename: safeFilename, path: filePath, codeLength: code.length }
    };
  } catch (err: any) {
    return {
      success: false,
      message: `Failed to write code file: ${err.message}`
    };
  }
}

// 2. Run Code from Workspace
export function runCode(filename: string): Promise<ToolResult> {
  return new Promise((resolve) => {
    try {
      const safeFilename = path.basename(filename);
      const filePath = path.join(WORKSPACE_DIR, safeFilename);

      if (!fs.existsSync(filePath)) {
        return resolve({
          success: false,
          message: `File ${safeFilename} does not exist in workspace.`
        });
      }

      // Determine execution command based on extension/language
      const ext = path.extname(safeFilename);
      let cmd = "";

      if (ext === ".js") {
        cmd = `node "${filePath}"`;
      } else if (ext === ".ts") {
        cmd = `npx tsx "${filePath}"`;
      } else if (ext === ".py") {
        cmd = `python3 "${filePath}"`;
      } else if (ext === ".sh") {
        cmd = `bash "${filePath}"`;
      } else {
        return resolve({
          success: false,
          message: `Running files with extension ${ext} is not supported directly. Supported extensions are .js, .ts, .py, .sh.`
        });
      }

      // Execute code with 5-second timeout
      exec(cmd, { timeout: 5000 }, (error, stdout, stderr) => {
        if (error) {
          if (error.killed) {
            return resolve({
              success: false,
              message: `Execution timed out (limit: 5 seconds)`,
              output: stdout + "\n" + "[Timeout Error]"
            });
          }
          return resolve({
            success: false,
            message: `Execution failed with error: ${error.message}`,
            output: stdout + "\n" + stderr
          });
        }

        resolve({
          success: true,
          message: `Successfully executed ${safeFilename}`,
          output: stdout || "[No output returned from execution]"
        });
      });

    } catch (err: any) {
      resolve({
        success: false,
        message: `Failed to execute code: ${err.message}`
      });
    }
  });
}

// 3. Screen Capture + Continuous Real-Time Gemini Vision Analysis
const DEFAULT_VISION_AGENT_URL = process.env.VISION_AGENT_URL || "http://127.0.0.1:8200";
const DEFAULT_BRIDGE_URL = process.env.ERA_BRIDGE_URL || "http://127.0.0.1:8100";
const VISION_API_KEY = process.env.VISION_AGENT_API_KEY || "era_vision_secret_key_2026";
const BRIDGE_API_KEY = process.env.ERA_BRIDGE_API_KEY || "era_bridge_secret_key_2026";

async function fetchLiveVisionState(): Promise<any> {
  // 1. Try ERA Bridge passthrough
  try {
    const res = await fetch(`${DEFAULT_BRIDGE_URL}/v1/vision/screen`, {
      headers: {
        "X-Era-Bridge-Key": BRIDGE_API_KEY,
        "Authorization": `Bearer ${BRIDGE_API_KEY}`,
      },
      signal: AbortSignal.timeout(3000),
    });
    if (res.ok) {
      const data = await res.json();
      if (data.current_state) return data.current_state;
    }
  } catch (e) {}

  // 2. Try direct ERA Vision Agent
  try {
    const res = await fetch(`${DEFAULT_VISION_AGENT_URL}/v1/vision/current-state`, {
      headers: { "X-Vision-Agent-Key": VISION_API_KEY },
      signal: AbortSignal.timeout(3000),
    });
    if (res.ok) {
      const data = await res.json();
      if (data.current_state) return data.current_state;
    }
  } catch (e) {}

  // 3. Auto-start Vision Agent if off/idle
  try {
    await fetch(`${DEFAULT_VISION_AGENT_URL}/v1/vision/start`, {
      method: "POST",
      headers: { "X-Vision-Agent-Key": VISION_API_KEY },
      signal: AbortSignal.timeout(3000),
    });
  } catch (e) {}

  return null;
}

async function fetchLatestChartAnalysis(): Promise<any> {
  try {
    const res = await fetch(`${DEFAULT_BRIDGE_URL}/v1/vision/chart/latest`, {
      headers: {
        "X-Era-Bridge-Key": BRIDGE_API_KEY,
        "Authorization": `Bearer ${BRIDGE_API_KEY}`,
      },
      signal: AbortSignal.timeout(3000),
    });
    if (res.ok) {
      const data = await res.json();
      return data.chart || null;
    }
  } catch (e) {}
  return null;
}

function triggerNativeDesktopScreenshot(): Promise<boolean> {
  return new Promise((resolve) => {
    const screenPath = path.join(WORKSPACE_DIR, "current_screen.png");
    const escapedPath = screenPath.replace(/'/g, "''");
    const psCmd = `Add-Type -AssemblyName System.Windows.Forms,System.Drawing; $b=[System.Windows.Forms.Screen]::PrimaryScreen.Bounds; $bmp=New-Object System.Drawing.Bitmap($b.Width,$b.Height); $g=[System.Drawing.Graphics]::FromImage($bmp); $g.CopyFromScreen($b.Location,[System.Drawing.Point]::Empty,$b.Size); $bmp.Save('${escapedPath}',[System.Drawing.Imaging.ImageFormat]::Png); $g.Dispose(); $bmp.Dispose(); Write-Output 'OK'`;
    exec(`powershell -NoProfile -Command "${psCmd}"`, { timeout: 6000 }, (err) => {
      if (err) {
        console.warn("[captureScreen] Native screenshot error:", err.message);
      }
      resolve(fs.existsSync(screenPath));
    });
  });
}

// 3. Screen Capture + Continuous Real-Time Gemini Vision Analysis
// Connects to ERA Vision Agent (http://127.0.0.1:8200) & ERA Bridge Gateway (http://127.0.0.1:8100)
// for 100% accurate, live physical desktop screen awareness and trading chart technical analysis.
export async function captureScreen(): Promise<ToolResult> {
  // Trigger fresh native desktop screenshot in background
  await triggerNativeDesktopScreenshot().catch(() => {});

  const screenPath = path.join(WORKSPACE_DIR, "current_screen.png");
  const hasPhysicalScreen = fs.existsSync(screenPath);

  // Fetch perception from 24/7 ERA Vision Agent
  const liveState = await fetchLiveVisionState();
  let chartAnalysis: any = null;
  if (liveState?.state?.chart_detected) {
    chartAnalysis = await fetchLatestChartAnalysis();
  }

  let visionAgentText = "";
  if (liveState) {
    const s = liveState.state || {};
    const w = liveState.window || {};
    visionAgentText += `[ERA VISION PERCEPTION - LIVE ACTIVE WINDOW]\n`;
    visionAgentText += `- Active Application: ${s.application || w.process_name || "Unknown"}\n`;
    visionAgentText += `- Window Title: ${s.window_title || w.title || "None"}\n`;
    visionAgentText += `- Screen Summary: ${s.summary || "Screen is being observed"}\n`;
    if (s.current_activity) {
      visionAgentText += `- Current Activity: ${s.current_activity}\n`;
    }
    if (s.visible_elements?.length) {
      visionAgentText += `- Visible Elements: ${s.visible_elements.map((e: any) => `${e.label} (${e.element_type})`).join(", ")}\n`;
    }
    if (s.important_text?.length) {
      visionAgentText += `- Text on Screen: ${s.important_text.join("; ")}\n`;
    }
    if (s.errors?.length) {
      visionAgentText += `- Visible Errors/Alerts: ${s.errors.join(", ")}\n`;
    }

    if (chartAnalysis) {
      visionAgentText += `\n[TRADING CHART ANALYSIS]\n`;
      visionAgentText += `- Asset: ${chartAnalysis.asset || "Chart"} (${chartAnalysis.timeframe || "N/A"})\n`;
      visionAgentText += `- Trend: ${chartAnalysis.current_trend} (Strength: ${chartAnalysis.trend_strength || "moderate"})\n`;
      visionAgentText += `- Short-Term Prediction: ${chartAnalysis.short_term_prediction || "Consolidating"}\n`;
      visionAgentText += `- Bullish Prob: ${(chartAnalysis.bullish_probability * 100).toFixed(0)}%, Bearish Prob: ${(chartAnalysis.bearish_probability * 100).toFixed(0)}%\n`;
      if (chartAnalysis.support_levels?.length) {
        visionAgentText += `- Support Levels: ${chartAnalysis.support_levels.map((l: any) => l.price_label).join(", ")}\n`;
      }
      if (chartAnalysis.resistance_levels?.length) {
        visionAgentText += `- Resistance Levels: ${chartAnalysis.resistance_levels.map((l: any) => l.price_label).join(", ")}\n`;
      }
      if (chartAnalysis.visible_indicators?.length) {
        visionAgentText += `- Indicators: ${chartAnalysis.visible_indicators.join(", ")}\n`;
      }
    }
  }

  // If screenshot file is available, also run Gemini Vision for deep visual details
  let directVisionText = "";
  if (hasPhysicalScreen) {
    try {
      const keys = loadKeys();
      const apiKey = keys.geminiApiKey || process.env.GEMINI_API_KEY;
      if (apiKey && !apiKey.startsWith("••••") && apiKey.length > 10) {
        const imageBuffer = fs.readFileSync(screenPath);
        const base64Image = imageBuffer.toString("base64");
        const genAI = new GoogleGenAI({ apiKey });

        const response = await genAI.models.generateContent({
          model: "gemini-2.0-flash",
          contents: [
            {
              role: "user",
              parts: [
                {
                  inlineData: {
                    mimeType: "image/png",
                    data: base64Image,
                  }
                },
                {
                  text: `You are ERA's real-time screen vision analyst. Look closely at this EXACT screenshot of the user's laptop desktop right now.
Provide a completely accurate, truthful description:
1. Active application and window title currently visible on screen
2. Actual text, content, tabs, open documents, or code visible
3. Any open dialogs, errors, or notifications
IMPORTANT: Be 100% faithful to this screenshot. Do NOT invent, assume, or hallucinate anything not visible in the image.`
                }
              ]
            }
          ]
        });
        directVisionText = response.text ?? "";
      }
    } catch (err: any) {
      console.warn("[captureScreen] Direct Gemini vision analysis note:", err.message);
    }
  }

  // Strict Anti-Hallucination Guard: If neither physical screenshot nor vision agent is active, never hallucinate
  if (!hasPhysicalScreen && !liveState) {
    return {
      success: false,
      message: "Boss, main abhi aapki screen nahi dekh pa raha hoon kyunki display capture ya Gemini API key configure nahi hai.",
      data: {
        hasScreen: false,
        timestamp: new Date().toISOString(),
        analysis: "NO REAL-TIME SCREEN CAPTURE AVAILABLE. Do NOT invent or hallucinate what is on the screen. Tell the user clearly and honestly that you cannot see their screen right now because the display capture or Gemini API key is not active.",
      }
    };
  }

  const finalAnalysis = [visionAgentText, directVisionText ? `\n[REAL-TIME SCREENSHOT ANALYSIS]\n${directVisionText}` : ""]
    .filter(Boolean)
    .join("\n\n") || "Screen capture completed.";

  return {
    success: true,
    message: "Screen analyzed successfully using real-time desktop vision.",
    data: {
      hasScreen: true,
      timestamp: new Date().toISOString(),
      analysis: finalAnalysis,
      liveState,
      chartAnalysis,
      screenPath: hasPhysicalScreen ? screenPath : undefined,
    }
  };
}

// Read chats after getting verbal confirmation
export async function readScreenChats(contactName?: string, confirmed?: boolean): Promise<ToolResult> {
  if (confirmed !== true) {
    return {
      success: false,
      message: "CONFIRMATION REQUIRED: Ask the user for confirmation before reading private chats: 'Boss, kya main aapki screen pe khuli chats padh kar bataoon?'",
    };
  }

  const screenRes = await captureScreen();
  const liveChats = loadWhatsAppChats();

  let chatSummary = "Chat Reading (Confirmed by Boss):\n\n";
  if (screenRes.success && screenRes.data?.analysis) {
    chatSummary += `[ON-SCREEN VISIBLE CHATS & TEXT]\n${screenRes.data.analysis}\n\n`;
  }

  if (liveChats.length > 0) {
    const filtered = contactName
      ? liveChats.filter(c => c.contactName.toLowerCase().includes(contactName.toLowerCase()))
      : liveChats.slice(0, 10);
    chatSummary += `[RECORDED MESSAGES]\n` + filtered.map(c => `[${c.timestamp}] ${c.contactName}: ${c.message}`).join("\n");
  }

  return {
    success: true,
    message: "Successfully read chat contents after boss confirmation.",
    data: { analysis: chatSummary }
  };
}

// 3.5. Open File Tool (Finds and opens a file or project folder on any hard drive)
// 3.5. Open File Tool (Finds and opens a file or project folder on any hard drive)
export async function openFile(filename: string, openWith?: string): Promise<ToolResult> {
  try {
    const cleanName = filename.trim();
    const resolvedOpenWith = (openWith || "default").toLowerCase();
    const userProfile = process.env.USERPROFILE || process.env.HOME || "C:\\Users\\User";

    // 1. Direct path check
    const safeFilename = path.basename(cleanName);
    const workspacePath = path.join(WORKSPACE_DIR, safeFilename);

    let targetPath: string | null = null;

    if (fs.existsSync(cleanName)) {
      targetPath = cleanName;
    } else if (fs.existsSync(workspacePath)) {
      targetPath = workspacePath;
    } else {
      // 2. Discover all connected drives dynamically (C:, D:, E:, etc.)
      const searchRoots: string[] = [];
      const userFolders = ["Downloads", "Desktop", "Documents", "Pictures", "Videos", "Music"];
      for (const f of userFolders) {
        const p = path.join(userProfile, f);
        if (fs.existsSync(p)) searchRoots.push(p);
      }
      searchRoots.push(userProfile);

      // Check all possible drive letters C through Z
      for (let i = 67; i <= 90; i++) {
        const driveLetter = String.fromCharCode(i) + ":\\";
        if (fs.existsSync(driveLetter) && !searchRoots.includes(driveLetter)) {
          searchRoots.push(driveLetter);
        }
      }

      const searchName = safeFilename.toLowerCase();
      const skipDirs = new Set(["$recycle.bin", "system volume information", "windows", "node_modules", ".git", ".venv", "temp"]);

      // First pass: top-level scan
      for (const root of searchRoots) {
        try {
          const items = fs.readdirSync(root);
          const directMatch = items.find(item => item.toLowerCase() === searchName || item.toLowerCase().includes(searchName));
          if (directMatch) {
            targetPath = path.join(root, directMatch);
            break;
          }
        } catch (e) {}
      }

      // Second pass: deep recursive scan up to depth 4
      if (!targetPath) {
        for (const root of searchRoots) {
          try {
            const queue: Array<{ dir: string; depth: number }> = [{ dir: root, depth: 0 }];
            while (queue.length > 0 && !targetPath) {
              const current = queue.shift()!;
              if (current.depth > 4) continue;

              let entries: fs.Dirent[] = [];
              try {
                entries = fs.readdirSync(current.dir, { withFileTypes: true });
              } catch (e) {
                continue;
              }

              for (const entry of entries) {
                const nameLow = entry.name.toLowerCase();
                if (entry.isFile() && (nameLow === searchName || nameLow.includes(searchName))) {
                  targetPath = path.join(current.dir, entry.name);
                  break;
                } else if (entry.isDirectory() && !skipDirs.has(nameLow) && !nameLow.startsWith(".")) {
                  queue.push({ dir: path.join(current.dir, entry.name), depth: current.depth + 1 });
                }
              }
            }
          } catch (e) {}
          if (targetPath) break;
        }
      }
    }

    if (targetPath) {
      const agentRes = await executeAgentCommand("open_file", { file_name: targetPath, open_with: resolvedOpenWith });
      if (agentRes && agentRes.success) {
        return {
          success: true,
          message: agentRes.message || `Successfully opened "${path.basename(targetPath)}" on your laptop.`,
          data: { filename: path.basename(targetPath), path: targetPath, openWith: resolvedOpenWith }
        };
      }

      // Fallback native launch
      if (resolvedOpenWith.includes("vscode") || resolvedOpenWith.includes("code")) {
        exec(`code "${targetPath}"`, (err) => {
          if (err) exec(`start "" "${targetPath}"`);
        });
        return {
          success: true,
          message: `Successfully opened "${path.basename(targetPath)}" in Visual Studio Code.`,
          data: { filename: path.basename(targetPath), path: targetPath, openWith: "vscode" }
        };
      } else {
        exec(`start "" "${targetPath}"`);
        return {
          success: true,
          message: `Successfully opened "${path.basename(targetPath)}" on your laptop.`,
          data: { filename: path.basename(targetPath), path: targetPath, openWith: resolvedOpenWith }
        };
      }
    }

    // 3. Forward to Python Local Agent to check its multi-drive recursive and PowerShell search
    const agentSearchRes = await executeAgentCommand("open_file", { file_name: cleanName, open_with: resolvedOpenWith });
    if (agentSearchRes && agentSearchRes.success) {
      return {
        success: true,
        message: agentSearchRes.message || `Found and opened "${cleanName}" on your laptop.`,
        data: (agentSearchRes as any).data,
      };
    }

    return {
      success: false,
      message: agentSearchRes?.message || `File "${cleanName}" not found on your laptop drives. Please check the file name or location.`,
    };
  } catch (err: any) {
    return {
      success: false,
      message: `Failed to open laptop file: ${err.message}`
    };
  }
}

// 4. WhatsApp Web Integration
const WHATSAPP_CHATS_FILE = path.join(CONFIG_DIR, "whatsapp_chats.json");

export interface WhatsAppMessage {
  contactName: string;
  message: string;
  timestamp: string;
  status: "sent" | "failed";
}

const WHATSAPP_CONTACTS_FILE = path.join(CONFIG_DIR, "whatsapp_contacts.json");

export interface Contact {
  name: string;
  aliases: string[];
  phone: string;
  shortPhone?: string;
}

export function loadContacts(): Contact[] {
  if (fs.existsSync(WHATSAPP_CONTACTS_FILE)) {
    try {
      return JSON.parse(fs.readFileSync(WHATSAPP_CONTACTS_FILE, "utf8"));
    } catch (err) {
      console.error("Error reading contacts file:", err);
    }
  }
  // No hardcoded numbers are included in Eera's code anymore
  return [
    { name: "Bhaiya", aliases: ["bhaiya", "bhaiyya", "bhayya", "bhaya", "brother", "my brother", "bhai", "bro", "veerji"], phone: "" },
    { name: "Sakshi", aliases: ["sakshi", "sakshii", "saksi", "sister", "my sister", "sis"], phone: "" },
    { name: "Mom", aliases: ["mom", "mother", "mummy", "maa", "mommy", "mama", "mamma"], phone: "" },
    { name: "Dad", aliases: ["dad", "father", "papa", "daddy", "pop"], phone: "" },
    { name: "Bestie", aliases: ["bestie", "friend", "best friend", "babu", "shona"], phone: "" }
  ];
}

export function saveContacts(contacts: Contact[]): void {
  fs.writeFileSync(WHATSAPP_CONTACTS_FILE, JSON.stringify(contacts, null, 2), "utf8");
}

export function resolveContact(query: string): { name: string; phone: string } {
  if (!query) return { name: "Unknown", phone: "" };

  const contacts = loadContacts();
  const cleanQuery = query.trim().toLowerCase();
  
  // 1. If the query consists of phone digits, try to find a contact that matches this number.
  // This allows Eera to find the person's name dynamically without having the number hardcoded in her TS code!
  const queryDigits = query.replace(/[^0-9]/g, '');
  if (queryDigits && queryDigits.length >= 4) {
    for (const contact of contacts) {
      if (contact.phone) {
        const cleanContactPhone = contact.phone.replace(/[^0-9]/g, '');
        const cleanShortPhone = (contact.shortPhone || "").replace(/[^0-9]/g, '') || cleanContactPhone.slice(-10);
        if (
          queryDigits === cleanContactPhone || 
          queryDigits === cleanShortPhone || 
          cleanContactPhone.endsWith(queryDigits) || 
          queryDigits.endsWith(cleanShortPhone)
        ) {
          // Found by phone number! Send/open by their actual name.
          return { name: contact.name, phone: contact.phone };
        }
      }
    }
  }

  // 2. Try matching by exact name or alias (case-insensitive)
  for (const contact of contacts) {
    if (contact.name.toLowerCase() === cleanQuery || contact.aliases.includes(cleanQuery)) {
      return { name: contact.name, phone: contact.phone || "" };
    }
  }

  // 3. Try matching by fuzzy / similar phonetic spelling (e.g. bhaiya vs bhaiyya)
  const normalizeSpelling = (s: string) => {
    return s.toLowerCase()
      .replace(/yy/g, 'y')   // collapse double y -> y
      .replace(/sh/g, 's')   // treat sh/s interchangeably for phonetic typos
      .replace(/kh/g, 'k')   // treat kh/k interchangeably
      .replace(/aa/g, 'a')   // collapse double aa -> a
      .replace(/ee/g, 'i')   // collapse double ee -> i
      .replace(/oo/g, 'u')   // collapse double oo -> u
      .replace(/(.)\1+/g, '$1') // collapse all double letters
      .replace(/[^a-z]/g, '');  // keep alphabetical only
  };

  const normQuery = normalizeSpelling(cleanQuery);
  if (normQuery.length > 1) {
    for (const contact of contacts) {
      if (normalizeSpelling(contact.name) === normQuery) {
        return { name: contact.name, phone: contact.phone || "" };
      }
      for (const alias of contact.aliases) {
        if (normalizeSpelling(alias) === normQuery) {
          return { name: contact.name, phone: contact.phone || "" };
        }
      }
    }
  }

  // Strictly return empty phone if not found in verified contacts
  return { name: query, phone: "" };
}

let lastSentWhatsappTimestamp = 0;
let lastSentWhatsappFingerprint = "";

export function sendWhatsAppMessage(contactName: string, message: string): ToolResult {
  try {
    const cleanMsg = (message || "").trim();
    const cleanContact = (contactName || "").trim();

    // Deduplication guard: ignore identical calls within 4 seconds
    const fingerprint = `${cleanContact}:::${cleanMsg}`;
    const now = Date.now();
    if (fingerprint === lastSentWhatsappFingerprint && (now - lastSentWhatsappTimestamp) < 4000) {
      console.log(`[sendWhatsAppMessage] Duplicate suppressed within 4s: ${fingerprint}`);
      return {
        success: true,
        message: `WhatsApp message already dispatched to "${cleanContact}".`,
      };
    }
    lastSentWhatsappFingerprint = fingerprint;
    lastSentWhatsappTimestamp = now;

    const resolved = resolveContact(cleanContact);

    // Read current chats
    let chats: WhatsAppMessage[] = [];
    if (fs.existsSync(WHATSAPP_CHATS_FILE)) {
      chats = JSON.parse(fs.readFileSync(WHATSAPP_CHATS_FILE, "utf8"));
    }

    const newMessage: WhatsAppMessage = {
      contactName: resolved.name,
      message,
      timestamp: new Date().toISOString(),
      status: "sent"
    };

    chats.unshift(newMessage);
    // Limit to 50 logs
    if (chats.length > 50) chats = chats.slice(0, 50);

    fs.writeFileSync(WHATSAPP_CHATS_FILE, JSON.stringify(chats, null, 2), "utf8");

    // Trigger local agent open_whatsapp command asynchronously
    executeAgentCommand("open_whatsapp", {
      phone: resolved.phone || contactName,
      message: message
    }).catch(err => {
      console.warn("[sendWhatsAppMessage] executeAgentCommand error:", err);
    });

    const displayPhone = resolved.phone || "Searching Contact Name on WhatsApp";

    return {
      success: true,
      message: `Successfully initiated WhatsApp message to "${resolved.name}" (${displayPhone})`,
      data: newMessage
    };
  } catch (err: any) {
    return {
      success: false,
      message: `Failed to send WhatsApp message: ${err.message}`
    };
  }
}

export function loadWhatsAppChats(): WhatsAppMessage[] {
  if (!fs.existsSync(WHATSAPP_CHATS_FILE)) return [];
  try {
    return JSON.parse(fs.readFileSync(WHATSAPP_CHATS_FILE, "utf8"));
  } catch {
    return [];
  }
}

export function getContacts(): ToolResult {
  try {
    const contacts = loadContacts();
    return {
      success: true,
      message: "Successfully retrieved contacts list",
      data: contacts
    };
  } catch (err: any) {
    return {
      success: false,
      message: `Failed to retrieve contacts list: ${err.message}`
    };
  }
}

// 5. Windows Phone Link Device Integration
export async function makePhoneCall(target: string): Promise<ToolResult> {
  try {
    const resolved = resolveContact(target);
    const phoneToCall = resolved.phone || target;
    const res = await executeAgentCommand("make_phone_call", { phone: phoneToCall });
    return {
      success: res.success,
      message: res.message,
      data: { target, resolvedPhone: phoneToCall }
    };
  } catch (err: any) {
    return {
      success: false,
      message: `Failed to make phone call via Phone Link: ${err.message}`
    };
  }
}

export async function readPhoneMessages(): Promise<ToolResult> {
  try {
    const res = await executeAgentCommand("read_phone_messages", { limit: 5 });
    return {
      success: res.success,
      message: res.message
    };
  } catch (err: any) {
    return {
      success: false,
      message: `Failed to read messages via Phone Link: ${err.message}`
    };
  }
}

export async function transferPhoneFiles(direction = "phone_to_laptop", fileName?: string): Promise<ToolResult> {
  try {
    const res = await executeAgentCommand("transfer_phone_files", { direction, file_name: fileName });
    return {
      success: res.success,
      message: res.message
    };
  } catch (err: any) {
    return {
      success: false,
      message: `Failed to transfer files via Phone Link: ${err.message}`
    };
  }
}

export async function getPhoneLinkStatus(): Promise<ToolResult> {
  try {
    const res = await executeAgentCommand("get_phone_link_status", {});
    return {
      success: res.success,
      message: res.message
    };
  } catch (err: any) {
    return {
      success: false,
      message: `Failed to check Phone Link status: ${err.message}`
    };
  }
}

import { submitOutcomeGoal, fetchOutcomeTaskStatus } from "./outcomeEngineClient";

export async function executeOutcomeGoal(goalPrompt: string): Promise<ToolResult> {
  try {
    const result = await submitOutcomeGoal(goalPrompt);
    if (!result || !result.success) {
      return {
        success: false,
        message: `Failed to submit outcome goal to Autonomous Engine: ${goalPrompt}`
      };
    }
    return {
      success: true,
      message: `ERA Autonomous Outcome Engine launched goal: "${result.objective}"`,
      data: result
    };
  } catch (err: any) {
    return {
      success: false,
      message: `Autonomous Outcome Engine error: ${err.message}`
    };
  }
}



