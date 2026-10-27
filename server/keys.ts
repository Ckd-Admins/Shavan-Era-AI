import fs from "fs";
import path from "path";
import crypto from "crypto";

let CONFIG_DIR = process.env.ERA_CONFIG_DIR || path.join(process.env.LOCALAPPDATA || process.env.USERPROFILE || process.cwd(), "ERA", "config");

try {
  if (!fs.existsSync(CONFIG_DIR)) {
    fs.mkdirSync(CONFIG_DIR, { recursive: true });
  }
} catch {
  CONFIG_DIR = path.join(process.cwd(), "config");
  try {
    if (!fs.existsSync(CONFIG_DIR)) {
      fs.mkdirSync(CONFIG_DIR, { recursive: true });
    }
  } catch {}
}

let KEYS_FILE = path.join(CONFIG_DIR, "keys.enc");
if (!fs.existsSync(KEYS_FILE)) {
  const localKeys = path.join(process.cwd(), "config", "keys.enc");
  if (fs.existsSync(localKeys)) {
    KEYS_FILE = localKeys;
  }
}

// Secret key for local AES encryption. In a real app this is derived, 
// here we use a consistent local hash.
const ENCRYPTION_KEY = crypto.scryptSync("era-companion-agent-secret-pass", "era-salt", 32);
const IV_LENGTH = 16;

export interface APIKeys {
  geminiApiKey: string;
  claudeApiKey: string;
  openaiApiKey: string;
  whatsappStatus: "connected" | "disconnected";
  preferredModel: "gemini" | "claude" | "gpt";
  screenStreamEnabled?: boolean;
  screenStreamFps?: number;
  screenStreamQuality?: number;
  visualPersistenceMode?: "realtime_continuous_feed" | "snapshot_on_demand";
  descriptions?: Record<string, string>;
}

const DEFAULT_KEYS: APIKeys = {
  geminiApiKey: process.env.GEMINI_API_KEY || "",
  claudeApiKey: "",
  openaiApiKey: "",
  whatsappStatus: "disconnected",
  preferredModel: "gemini",
  screenStreamEnabled: true,
  screenStreamFps: 10,
  screenStreamQuality: 0.65,
  visualPersistenceMode: "realtime_continuous_feed",
  descriptions: {
    geminiApiKey: "API Key for Google Gemini model access and multimodal analysis.",
    claudeApiKey: "API Key for Anthropic Claude model integration.",
    openaiApiKey: "API Key for OpenAI GPT model integration.",
    whatsappStatus: "Current connection status for WhatsApp Companion bot integration.",
    preferredModel: "Default AI model selection for Era companion responses.",
    screenStreamEnabled: "Enable or disable real-time screen video feed streaming into Gemini Multimodal Live.",
    screenStreamFps: "Frame rate (frames per second) for continuous screen video streaming (default: 10 FPS).",
    screenStreamQuality: "JPEG compression quality for real-time video feed streaming (0.1 to 1.0).",
    visualPersistenceMode: "Visual perception mode: continuous real-time video feed or on-demand snapshot."
  }
};

export function encrypt(text: string): string {
  if (!text) return "";
  const iv = crypto.randomBytes(IV_LENGTH);
  const cipher = crypto.createCipheriv("aes-256-cbc", ENCRYPTION_KEY, iv);
  let encrypted = cipher.update(text, "utf8", "hex");
  encrypted += cipher.final("hex");
  return iv.toString("hex") + ":" + encrypted;
}

export function decrypt(text: string): string {
  if (!text) return "";
  try {
    const parts = text.split(":");
    const iv = Buffer.from(parts.shift() || "", "hex");
    const encryptedText = Buffer.from(parts.join(":"), "hex");
    const decipher = crypto.createDecipheriv("aes-256-cbc", ENCRYPTION_KEY, iv);
    let decrypted = decipher.update(encryptedText);
    decrypted = Buffer.concat([decrypted, decipher.final()]);
    return decrypted.toString();
  } catch (err) {
    console.error("Failed to decrypt keys. Reinitializing keys file.", err);
    return "";
  }
}

export function loadKeys(): APIKeys {
  if (!fs.existsSync(KEYS_FILE)) {
    saveKeys(DEFAULT_KEYS);
    return DEFAULT_KEYS;
  }
  try {
    const encryptedData = fs.readFileSync(KEYS_FILE, "utf8");
    const decryptedData = decrypt(encryptedData);
    if (!decryptedData) {
      saveKeys(DEFAULT_KEYS);
      return DEFAULT_KEYS;
    }
    const parsed: APIKeys = JSON.parse(decryptedData);
    if (!parsed.descriptions) {
      parsed.descriptions = DEFAULT_KEYS.descriptions;
      saveKeys(parsed);
    }
    return parsed;
  } catch (err) {
    console.error("Error loading keys:", err);
    return DEFAULT_KEYS;
  }
}

export function saveKeys(keys: Partial<APIKeys>): APIKeys {
  let current: APIKeys = DEFAULT_KEYS;
  if (fs.existsSync(KEYS_FILE)) {
    try {
      const encryptedData = fs.readFileSync(KEYS_FILE, "utf8");
      const decryptedData = decrypt(encryptedData);
      if (decryptedData) {
        current = JSON.parse(decryptedData);
      }
    } catch (e) {
      // Fallback to DEFAULT_KEYS if file read or parse fails
    }
  }

  const updated: APIKeys = {
    ...current,
    ...keys,
    descriptions: {
      ...(DEFAULT_KEYS.descriptions || {}),
      ...(current.descriptions || {}),
      ...(keys.descriptions || {})
    }
  };
  
  try {
    const dataString = JSON.stringify(updated);
    const encryptedData = encrypt(dataString);
    fs.writeFileSync(KEYS_FILE, encryptedData, "utf8");
    return updated;
  } catch (err) {
    console.error("Error saving keys:", err);
    throw err;
  }
}
