/**
 * Agent Bridge Module for Era Voice Assistant.
 * 
 * Bridges the Node.js Express / Gemini Multimodal Live API Voice Assistant
 * to the Era Python Local Agent REST API (FastAPI server running on http://127.0.0.1:8000).
 */

import { spawn } from "child_process";
import * as fs from "fs";
import * as path from "path";

const DEFAULT_AGENT_URL = process.env.ERA_AGENT_URL || "http://127.0.0.1:8000";
const DEFAULT_BRIDGE_URL = process.env.ERA_BRIDGE_URL || "http://127.0.0.1:8100";
const BRIDGE_API_KEY = process.env.ERA_BRIDGE_API_KEY || "era_bridge_secret_key_2026";

export interface AgentExecuteResult {
  success: boolean;
  message: string;
}

export interface AgentStatusResult {
  status: string;
  agent: string;
  version: string;
  available_commands: number;
}

export interface AgentCommandSpec {
  description: string;
  parameters: Array<{
    name: string;
    type: string;
    description: string;
    required: boolean;
    default?: any;
  }>;
}

/**
 * Checks if the Era Python Local Agent or Era Bridge API server is running and online.
 */
export async function checkAgentStatus(): Promise<AgentStatusResult | null> {
  // 1. Try Era Local Agent directly (port 8000)
  try {
    const response = await fetch(`${DEFAULT_AGENT_URL}/status`, {
      method: "GET",
      headers: { "Content-Type": "application/json" },
      signal: AbortSignal.timeout(3000),
    });

    if (response.ok) {
      const data = (await response.json()) as AgentStatusResult;
      return data;
    }
  } catch (err: any) {
    console.warn(`[AgentBridge] Could not connect to Python Agent on ${DEFAULT_AGENT_URL}: ${err.message}`);
  }

  // 2. Fallback to Era Bridge Gateway (port 8100)
  try {
    const response = await fetch(`${DEFAULT_BRIDGE_URL}/v1/status`, {
      method: "GET",
      headers: { "Content-Type": "application/json" },
      signal: AbortSignal.timeout(3000),
    });

    if (response.ok) {
      const data = await response.json();
      return {
        status: data.status,
        agent: "Era Bridge Gateway",
        version: data.bridge_version,
        available_commands: data.agent_status?.available_commands || 13,
      };
    }
  } catch (err: any) {
    console.warn(`[AgentBridge] Could not connect to Era Bridge Gateway on ${DEFAULT_BRIDGE_URL}: ${err.message}`);
  }

  return null;
}

/**
 * Fetches specifications of all available commands from the Python Local Agent.
 */
export async function fetchAgentCommands(): Promise<Record<string, AgentCommandSpec> | null> {
  try {
    const response = await fetch(`${DEFAULT_AGENT_URL}/commands`, {
      method: "GET",
      headers: { "Content-Type": "application/json" },
      signal: AbortSignal.timeout(3000),
    });

    if (!response.ok) return null;
    const data = await response.json();
    return data.commands || null;
  } catch (err: any) {
    console.warn(`[AgentBridge] Error fetching command specs: ${err.message}`);
    return null;
  }
}

/**
 * Sends a command execution request to the Era Python Local Agent or Era Bridge Gateway REST API.
 * 
 * @param command - The name of the registered Python command (e.g. "open_notepad", "open_camera", "open_app")
 * @param params - Optional parameters object (e.g. { app_name: "vscode" })
 * @returns AgentExecuteResult containing success status and descriptive message.
 */
export async function executeAgentCommand(
  command: string,
  params: Record<string, any> = {}
): Promise<AgentExecuteResult> {
  console.log(`[AgentBridge] Invoking command '${command}' on Python Agent (${DEFAULT_AGENT_URL}) with params:`, params);

  const AGENT_API_KEY = process.env.ERA_AGENT_API_KEY || "era_internal_local_agent_key";

  // 1. Try Era Local Agent directly
  try {
    const response = await fetch(`${DEFAULT_AGENT_URL}/execute`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Era-Agent-Key": AGENT_API_KEY,
      },
      body: JSON.stringify({
        command: command.trim(),
        params: params || {},
      }),
      signal: AbortSignal.timeout(6000),
    });

    if (response.ok) {
      const result = (await response.json()) as AgentExecuteResult;
      console.log(`[AgentBridge] Execution result for '${command}':`, result);
      return result;
    } else {
      const errText = await response.text().catch(() => "");
      console.warn(`[AgentBridge] Direct agent returned HTTP ${response.status}: ${errText}`);
    }
  } catch (err: any) {
    console.warn(`[AgentBridge] Direct agent execution failed, trying Era Bridge: ${err.message}`);
  }

  // 2. Fallback: Try Era Bridge Gateway
  try {
    const response = await fetch(`${DEFAULT_BRIDGE_URL}/v1/execute`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Era-Bridge-Key": BRIDGE_API_KEY,
        "Authorization": `Bearer ${BRIDGE_API_KEY}`,
      },
      body: JSON.stringify({
        command: command.trim(),
        params: params || {},
      }),
      signal: AbortSignal.timeout(4000),
    });

    if (response.ok) {
      const data = await response.json();
      return {
        success: data.state === "success",
        message: data.message,
      };
    }
  } catch (err: any) {
    console.error(`[AgentBridge] Bridge fallback execution error: ${err.message}`);
  }

  // 3. Fallback: Windows Native Direct Launch (Completely bypasses PowerShell & COM)
  const cmd = command.toLowerCase().trim();

  if (cmd === "open_notepad") {
    spawn("notepad.exe", [], { detached: true, stdio: "ignore" }).unref();
    return { success: true, message: "Notepad opened successfully." };
  }

  if (cmd === "open_calculator") {
    spawn("calc.exe", [], { detached: true, stdio: "ignore" }).unref();
    return { success: true, message: "Calculator opened successfully." };
  }

  if (cmd === "open_camera") {
    spawn("explorer.exe", ["microsoft.windows.camera:"], { detached: true, stdio: "ignore" }).unref();
    return { success: true, message: "Camera opened successfully." };
  }

  if (cmd === "open_file_explorer") {
    spawn("explorer.exe", [], { detached: true, stdio: "ignore" }).unref();
    return { success: true, message: "File Explorer opened successfully." };
  }

  if (cmd === "open_chrome") {
    const chromePaths = [
      "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
      "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
      path.join(process.env.LOCALAPPDATA || "", "Google", "Chrome", "Application", "chrome.exe"),
    ];
    for (const cp of chromePaths) {
      if (fs.existsSync(cp)) {
        spawn(cp, [], { detached: true, stdio: "ignore" }).unref();
        return { success: true, message: "Google Chrome opened successfully." };
      }
    }
    spawn("explorer.exe", ["https://www.google.com"], { detached: true, stdio: "ignore" }).unref();
    return { success: true, message: "Opened Google Chrome." };
  }

  if (cmd === "open_browser") {
    const url = params?.url || "https://www.google.com";
    if (url.toLowerCase().includes("whatsapp")) {
      return executeAgentCommand("open_whatsapp", params);
    }
    spawn("explorer.exe", [url], { detached: true, stdio: "ignore" }).unref();
    return { success: true, message: `Opened browser to ${url}.` };
  }

  if (cmd === "open_whatsapp") {
    const rawTarget = String(params?.phone || params?.target || "").trim();
    const targetMsg = String(params?.message || "").trim();
    let digits = rawTarget.replace(/[^0-9]/g, "");
    if (digits.length === 10) digits = "91" + digits;
    else if (digits.length === 11 && digits.startsWith("0")) digits = "91" + digits.slice(1);

    const encoded = encodeURIComponent(targetMsg);
    if (digits.length >= 7) {
      const waUrl = `whatsapp://send?phone=${digits}&text=${encoded}`;
      spawn("explorer.exe", [waUrl], { detached: true, stdio: "ignore" }).unref();
      return { success: true, message: `WhatsApp opened for +${digits} and message: '${targetMsg}'` };
    } else {
      spawn("explorer.exe", ["whatsapp:"], { detached: true, stdio: "ignore" }).unref();
      return { success: true, message: `WhatsApp opened for ${rawTarget || "user"}.` };
    }
  }

  if (cmd === "open_app" && params?.app_name) {
    const rawApp = String(params.app_name).trim();
    const cleanApp = rawApp.toLowerCase().replace(/[^a-z0-9]/g, "");

    // VS Code
    if (["vscode", "code", "visualstudiocode"].includes(cleanApp)) {
      const codePaths = [
        path.join(process.env.LOCALAPPDATA || "", "Programs", "Microsoft VS Code", "Code.exe"),
        "C:\\Program Files\\Microsoft VS Code\\Code.exe",
        "C:\\Program Files (x86)\\Microsoft VS Code\\Code.exe",
      ];
      for (const cp of codePaths) {
        if (fs.existsSync(cp)) {
          spawn(cp, [], { detached: true, stdio: "ignore" }).unref();
          return { success: true, message: "VS Code opened successfully." };
        }
      }
      spawn("explorer.exe", ["code"], { detached: true, stdio: "ignore" }).unref();
      return { success: true, message: "VS Code opened successfully." };
    }

    // Chrome
    if (["chrome", "googlechrome", "google"].includes(cleanApp)) {
      const chromePaths = [
        "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
        "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
        path.join(process.env.LOCALAPPDATA || "", "Google", "Chrome", "Application", "chrome.exe"),
      ];
      for (const cp of chromePaths) {
        if (fs.existsSync(cp)) {
          spawn(cp, [], { detached: true, stdio: "ignore" }).unref();
          return { success: true, message: "Google Chrome opened successfully." };
        }
      }
      spawn("explorer.exe", ["https://www.google.com"], { detached: true, stdio: "ignore" }).unref();
      return { success: true, message: "Google Chrome opened." };
    }

    // Canva
    if (cleanApp.includes("canva")) {
      const canvaPath = path.join(process.env.LOCALAPPDATA || "", "Programs", "Canva", "Canva.exe");
      if (fs.existsSync(canvaPath)) {
        spawn(canvaPath, [], { detached: true, stdio: "ignore" }).unref();
        return { success: true, message: "Canva opened successfully." };
      }
      spawn("explorer.exe", ["shell:AppsFolder\\com.canva.CanvaDesktop"], { detached: true, stdio: "ignore" }).unref();
      return { success: true, message: "Canva opened successfully." };
    }

    // WhatsApp
    if (cleanApp.includes("whatsapp")) {
      spawn("explorer.exe", ["shell:AppsFolder\\5319275A.WhatsAppDesktop_cv1g1gvanyjgm!App"], { detached: true, stdio: "ignore" }).unref();
      return { success: true, message: "WhatsApp opened successfully." };
    }

    // Xbox
    if (cleanApp.includes("xbox")) {
      spawn("explorer.exe", ["shell:AppsFolder\\Microsoft.GamingApp_8wekyb3d8bbwe!Microsoft.Xbox.App"], { detached: true, stdio: "ignore" }).unref();
      return { success: true, message: "Xbox opened successfully." };
    }

    // ChatGPT
    if (cleanApp.includes("chatgpt") || cleanApp.includes("openai")) {
      spawn("explorer.exe", ["shell:AppsFolder\\OpenAI.Codex_2p2nqsd0c76g0!App"], { detached: true, stdio: "ignore" }).unref();
      return { success: true, message: "ChatGPT opened successfully." };
    }

    // Claude
    if (cleanApp.includes("claude")) {
      spawn("explorer.exe", ["https://claude.ai"], { detached: true, stdio: "ignore" }).unref();
      return { success: true, message: "Opened Claude in your browser." };
    }

    // Calculator
    if (["calc", "calculator"].includes(cleanApp)) {
      spawn("calc.exe", [], { detached: true, stdio: "ignore" }).unref();
      return { success: true, message: "Calculator opened successfully." };
    }

    // Camera
    if (["camera", "webcam"].includes(cleanApp)) {
      spawn("explorer.exe", ["microsoft.windows.camera:"], { detached: true, stdio: "ignore" }).unref();
      return { success: true, message: "Camera opened successfully." };
    }

    // Notepad
    if (["notepad", "editor"].includes(cleanApp)) {
      spawn("notepad.exe", [], { detached: true, stdio: "ignore" }).unref();
      return { success: true, message: "Notepad opened successfully." };
    }

    // Microsoft Store
    if (["store", "microsoftstore", "windowsstore"].includes(cleanApp)) {
      spawn("explorer.exe", ["ms-windows-store:"], { detached: true, stdio: "ignore" }).unref();
      return { success: true, message: "Microsoft Store opened successfully." };
    }

    // Settings
    if (["settings", "pcsettings"].includes(cleanApp)) {
      spawn("explorer.exe", ["ms-settings:"], { detached: true, stdio: "ignore" }).unref();
      return { success: true, message: "Settings opened successfully." };
    }

    // Spotify
    if (cleanApp.includes("spotify")) {
      const spotifyPath = path.join(process.env.APPDATA || "", "Spotify", "Spotify.exe");
      if (fs.existsSync(spotifyPath)) {
        spawn(spotifyPath, [], { detached: true, stdio: "ignore" }).unref();
        return { success: true, message: "Spotify opened successfully." };
      }
      spawn("explorer.exe", ["spotify:"], { detached: true, stdio: "ignore" }).unref();
      return { success: true, message: "Spotify opened successfully." };
    }

    // General app launch via explorer.exe
    spawn("explorer.exe", [rawApp], { detached: true, stdio: "ignore" }).unref();
    return { success: true, message: `'${rawApp}' opened successfully.` };
  }

  return {
    success: false,
    message: `Could not reach Era Python Local Agent (${DEFAULT_AGENT_URL}) or Era Bridge Gateway (${DEFAULT_BRIDGE_URL}). Please ensure the services are running.`,
  };
}
