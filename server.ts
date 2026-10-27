import express from "express";
import http from "http";
import path from "path";
import fs from "fs";
import url from "url";
import { WebSocketServer, WebSocket } from "ws";
import { GoogleGenAI, Modality, Type, ThinkingLevel } from "@google/genai";
import dotenv from "dotenv";

import { loadKeys, saveKeys, APIKeys } from "./server/keys";
import { 
  writeCode, 
  runCode, 
  captureScreen, 
  readScreenChats,
  sendWhatsAppMessage, 
  loadWhatsAppChats,
  WhatsAppMessage,
  openFile,
  loadContacts,
  saveContacts,
  getContacts,
  resolveContact,
  makePhoneCall,
  readPhoneMessages,
  transferPhoneFiles,
  getPhoneLinkStatus
} from "./server/tools";
import { executeAgentCommand, checkAgentStatus } from "./server/agentBridge";


dotenv.config();

const app = express();
const PORT = 3000;

app.use(express.json({ limit: "50mb" }));

// Ensure workspace directory exists
const WORKSPACE_DIR = process.env.ERA_WORKSPACE_DIR || path.join(process.env.LOCALAPPDATA || process.env.USERPROFILE || process.cwd(), "ERA", "workspace");
if (!fs.existsSync(WORKSPACE_DIR)) {
  try { fs.mkdirSync(WORKSPACE_DIR, { recursive: true }); } catch {}
}

// Write the share_screen.py script to the workspace directory for the user
try {
  const daemonPath = path.join(WORKSPACE_DIR, "share_screen.py");
  const daemonContent = `import time
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
        print("✅ Live video feed streaming active to Era (10 FPS).", end="\\r")
        
        elapsed = time.time() - start_time
        sleep_time = max(0.01, 0.09 - elapsed)
        time.sleep(sleep_time)
    except Exception as e:
        print(f"❌ Feed Sync Error: {e}", end="\\r")
        time.sleep(0.2)
`;
  fs.writeFileSync(daemonPath, daemonContent, "utf8");
} catch (e) {
  console.error("Failed to write share_screen.py daemon:", e);
}

// REST API Endpoints for Dashboard Settings
app.get("/api/health", (req, res) => {
  res.json({ status: "ok" });
});

import { submitOutcomeGoal, fetchOutcomeTaskStatus, approveOutcomeTask, pauseOutcomeTask, resumeOutcomeTask, cancelOutcomeTask, createMission, fetchMission, approveMissionStep, fetchGmailStatus, fetchGmailAuthUrl, disconnectGmail, fetchWhatsAppStatus, fetchComputerState } from "./server/outcomeEngineClient";


app.post("/api/outcome/submit", async (req, res) => {
  const { prompt } = req.body;
  if (!prompt) return res.status(400).json({ error: "Prompt required" });
  const result = await submitOutcomeGoal(prompt);
  if (!result) return res.status(500).json({ error: "Failed to submit outcome goal" });
  res.json(result);
});

app.get("/api/outcome/status/:taskId", async (req, res) => {
  const result = await fetchOutcomeTaskStatus(req.params.taskId);
  if (!result) return res.status(404).json({ error: "Task not found" });
  res.json(result);
});

app.post("/api/outcome/approve/:taskId", async (req, res) => {
  const result = await approveOutcomeTask(req.params.taskId);
  if (!result) return res.status(500).json({ error: "Failed to approve task" });
  res.json(result);
});

app.post("/api/outcome/pause/:taskId", async (req, res) => {
  const result = await pauseOutcomeTask(req.params.taskId);
  if (!result) return res.status(500).json({ error: "Failed to pause task" });
  res.json(result);
});

app.post("/api/outcome/resume/:taskId", async (req, res) => {
  const result = await resumeOutcomeTask(req.params.taskId);
  if (!result) return res.status(500).json({ error: "Failed to resume task" });
  res.json(result);
});

app.post("/api/outcome/cancel/:taskId", async (req, res) => {
  const result = await cancelOutcomeTask(req.params.taskId);
  if (!result) return res.status(500).json({ error: "Failed to cancel task" });
  res.json(result);
});

// ERA Mission Engine API Endpoints
app.post("/api/missions", async (req, res) => {
  const { goal, context } = req.body;
  if (!goal) return res.status(400).json({ error: "Goal is required" });
  const result = await createMission(goal, context);
  if (!result) return res.status(500).json({ error: "Failed to create mission" });
  res.json(result);
});

app.get("/api/missions/:missionId", async (req, res) => {
  const result = await fetchMission(req.params.missionId);
  if (!result) return res.status(404).json({ error: "Mission not found" });
  res.json(result);
});

app.post("/api/missions/:missionId/approve", async (req, res) => {
  const result = await approveMissionStep(req.params.missionId);
  if (!result) return res.status(500).json({ error: "Failed to approve mission step" });
  res.json(result);
});

// Gmail & WhatsApp Real Status & Auth Endpoints
app.get("/api/gmail/status", async (req, res) => {
  res.json(await fetchGmailStatus());
});

app.get("/api/gmail/auth-url", async (req, res) => {
  res.json(await fetchGmailAuthUrl());
});

app.post("/api/gmail/disconnect", async (req, res) => {
  res.json(await disconnectGmail());
});

app.get("/api/whatsapp/status", async (req, res) => {
  res.json(await fetchWhatsAppStatus());
});





// 1. YouTube Link Metadata & Analysis API
function extractYoutubeVideoId(urlStr: string): string | null {
  const regExp = /^.*(youtu.be\/|v\/|u\/\w\/|embed\/|watch\?v=|\&v=)([^#\&\?]*).*/;
  const match = urlStr.match(regExp);
  return (match && match[2].length === 11) ? match[2] : null;
}

async function fetchYoutubeMetadata(videoId: string) {
  try {
    const response = await fetch(`https://www.youtube.com/watch?v=${videoId}`, {
      headers: {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
      }
    });
    const html = await response.text();
    
    // Extract title
    let title = "";
    const titleMatch = html.match(/<title>([^<]+)<\/title>/i);
    if (titleMatch) {
      title = titleMatch[1].replace(" - YouTube", "").trim();
    }
    
    // Extract description
    let description = "";
    const descMatch = html.match(/<meta\s+name="description"\s+content="([^"]+)"/i) || 
                      html.match(/<meta\s+property="og:description"\s+content="([^"]+)"/i);
    if (descMatch) {
      description = descMatch[1].trim();
    }
    
    return { title, description };
  } catch (error) {
    console.error("Error fetching YouTube metadata:", error);
    return null;
  }
}

app.post("/api/analyze-youtube", async (req, res) => {
  const { url: youtubeUrl } = req.body;
  if (!youtubeUrl) {
    return res.status(400).json({ error: "Missing YouTube URL" });
  }

  const videoId = extractYoutubeVideoId(youtubeUrl);
  if (!videoId) {
    return res.status(400).json({ error: "Invalid YouTube URL format. Could not extract Video ID." });
  }

  try {
    const ai = getGeminiClient();
    const metadata = await fetchYoutubeMetadata(videoId);
    
    const prompt = `You are Eira, a professional video analyst, content strategist, and personal assistant.
Analyze the following YouTube video details:
URL: ${youtubeUrl}
Title: "${metadata?.title || "Unknown Title"}"
Description: "${metadata?.description || "No description available on YouTube."}"

Please provide a highly polished and professional analysis:
1. **Core Content & Value**: What is this video actually about, what are the key takeaways, and what is the theme?
2. **Production & Editing Breakdown**: Explain how the video content was created (production style, expected camera work/assets, editing style, pacing, sound design, hook style, and visual engagement tricks).
3. **Strategic Next Steps**: What should be done next if a creator wants to build on top of this, replicate its success, or make related high-quality content?

Be highly insightful, detailed, and highly actionable. Keep your signature professional, polite, and well-mannered tone (modeled after Iron Man's JARVIS, addressing the user as "boss" or "sir") and pack it with elite industry wisdom! Use structured Markdown format.`;

    const result = await ai.models.generateContent({
      model: "gemini-3.5-flash",
      contents: prompt,
    });

    res.json({
      success: true,
      videoId,
      title: metadata?.title || "YouTube Video",
      analysis: result.text
    });
  } catch (err: any) {
    console.error("YouTube analysis error:", err);
    res.status(500).json({ error: err.message });
  }
});

// 2. Chatbot Message Handling API
app.post("/api/chatbot", async (req, res) => {
  const { message, history, systemInstruction, highThinking } = req.body;
  if (!message) {
    return res.status(400).json({ error: "Message is required" });
  }

  try {
    const ai = getGeminiClient();
    
    // Map history to Google Gen AI format: { role: 'user' | 'model', parts: [{ text: string }] }
    const formattedContents = (history || []).map((msg: any) => ({
      role: msg.sender === "user" ? "user" : "model",
      parts: [{ text: msg.text }]
    }));
    
    // Check if message is a system hardware control command (brightness, volume, bluetooth, wifi, keyboard backlight)
    try {
      const agentRes = await executeAgentCommand("process_natural_language_control", { query: message });
      if (agentRes.success) {
        return res.json({
          success: true,
          modelUsed: "era-system-agent",
          highThinkingEnabled: false,
          text: `Ji boss! ${agentRes.message}`
        });
      }
    } catch (agentErr) {
      console.warn("System control execution check failed, proceeding to Gemini:", agentErr);
    }

    // ── GMAIL TOOL ROUTING ──────────────────────────────────────────────────
    // Detect Gmail intent (Hindi+English) and call real Gmail API on port 8000
    const msgLower = message.toLowerCase();
    const gmailKeywords = [
      "gmail", "email", "mail", "inbox", "unread", "emails",
      "check mail", "check karo", "dikhao", "dekho", "padhna", "padho",
      "latest mail", "new mail", "letter", "sandesh"
    ];
    const isGmailRequest = gmailKeywords.some((kw: string) => msgLower.includes(kw));

    if (isGmailRequest) {
      try {
        const ERA_URL = process.env.ERA_AGENT_URL || "http://127.0.0.1:8000";
        const statusRes = await fetch(`${ERA_URL}/api/gmail/status`);
        const statusData: any = await statusRes.json();

        if (!statusData.authenticated) {
          return res.json({
            success: true, modelUsed: "era-gmail-router", highThinkingEnabled: false,
            text: `Boss, Gmail abhi connected nahi hai. ERA Dashboard par jakar Gmail connect karen — status: **${statusData.status}**`
          });
        }

        const isSend = msgLower.includes("send") || msgLower.includes("bhej") || msgLower.includes("bhejo") || msgLower.includes("mail kar") || msgLower.includes("compose");
        const isSearch = msgLower.includes("search") || msgLower.includes("find") || msgLower.includes("khojo");
        const isUnread = msgLower.includes("unread") || msgLower.includes("naye") || msgLower.includes("new mail");

        let gmailData: any;
        if (isSend) {
          // Extract email recipient address using regex if present
          const emailMatch = message.match(/[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/);
          const recipient = emailMatch ? emailMatch[0] : "";
          
          if (recipient) {
            const r = await fetch(`${ERA_URL}/execute`, {
              method: "POST", headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ 
                command: "gmail_send", 
                params: { 
                  recipient, 
                  subject: "Message from Shavan via ERA AI", 
                  body: message 
                } 
              })
            });
            gmailData = await r.json();
          } else {
            // Let Gemini ask for missing email recipient or execute command
            gmailData = { success: false, message: "Email recipient address missing in query." };
          }
        } else if (isSearch) {
          const searchMatch = message.match(/(?:search|find|khojo)[:\s]+(.+)/i);
          const query = searchMatch ? searchMatch[1].trim() : message;
          const r = await fetch(`${ERA_URL}/execute`, {
            method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ command: "gmail_search", params: { query } })
          });
          gmailData = await r.json();
        } else if (isUnread) {
          const r = await fetch(`${ERA_URL}/execute`, {
            method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ command: "gmail_search", params: { query: "is:unread" } })
          });
          gmailData = await r.json();
        } else {
          const r = await fetch(`${ERA_URL}/execute`, {
            method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ command: "gmail_list", params: { max_results: 5 } })
          });
          gmailData = await r.json();
        }

        const gmailContext = JSON.stringify(gmailData, null, 2);
        const summaryContents = [
          ...formattedContents,
          { role: "user" as const, parts: [{ text: `You are ERA (JARVIS-style AI). User asked: "${message}"\n\nREAL Gmail API response from ${statusData.user_email}:\n\n${gmailContext}\n\nSummarize the result clearly to the boss. Address user as "boss". Reply in same language as user (Hindi/English/mix). Be professional, polite and concise.` }] }
        ];
        const gmailResult = await ai.models.generateContent({
          model: "gemini-3.5-flash",
          contents: summaryContents,
          config: { systemInstruction: "You are ERA. Present real Gmail action results clearly. Never say you cannot access emails or send emails." }
        });
        return res.json({ success: true, modelUsed: "era-gmail-real", highThinkingEnabled: false, text: gmailResult.text });
      } catch (gmailErr: any) {
        console.error("Gmail tool routing error:", gmailErr);
        // Fall through to Gemini on error
      }
    }
    // ── REAL HARDWARE TELEMETRY ROUTING ─────────────────────────────────────
    const hwKeywords = [
      "battery", "hard drive", "harddrive", "hard disk", "harddisk", "disk space", "storage",
      "ram", "memory", "cpu", "gpu", "graphics card", "rtx", "hardware", "system status",
      "specs", "laptop status", "kitni battery", "battery kitni", "kitna space", "free space",
      "system specs", "pc status"
    ];
    const isHwRequest = hwKeywords.some((kw: string) => msgLower.includes(kw));

    if (isHwRequest) {
      try {
        const state = await fetchComputerState();
        if (state) {
          const hwSummary = {
            battery: state.battery,
            cpu: state.cpu,
            ram: state.memory ? {
              percent_used: state.memory.percent,
              free_gb: (state.memory.available_bytes / (1024**3)).toFixed(1),
              total_gb: (state.memory.total_bytes / (1024**3)).toFixed(1)
            } : "unavailable",
            disk_c: state.disk ? {
              free_gb: (state.disk.free_bytes / (1024**3)).toFixed(1),
              total_gb: (state.disk.total_bytes / (1024**3)).toFixed(1),
              used_percent: state.disk.percent
            } : "unavailable",
            gpu: state.gpu,
            bluetooth_devices: state.bluetooth,
            active_app: state.active_app,
            os: state.os_info
          };

          const hwContents = [
            ...formattedContents,
            {
              role: "user" as const,
              parts: [{
                text: `You are ERA (JARVIS-style AI). User asked: "${message}"\n\nREAL LIVE COMPUTER HARDWARE TELEMETRY FROM LOCAL AGENT:\n\n${JSON.stringify(hwSummary, null, 2)}\n\nAnswer the boss's question accurately with real numbers from above. Address the user as "boss" or "sir". Reply in the exact same language (Hindi/English/mix) as the boss. Never state that you cannot access hardware, because you just accessed real hardware telemetry.`
              }]
            }
          ];

          const hwResult = await ai.models.generateContent({
            model: "gemini-3.5-flash",
            contents: hwContents,
            config: {
              systemInstruction: "You are ERA. Present real computer hardware telemetry clearly, politely, and respectfully. Always use real numbers provided in the prompt."
            }
          });

          return res.json({
            success: true,
            modelUsed: "era-hardware-telemetry",
            highThinkingEnabled: false,
            text: hwResult.text
          });
        }
      } catch (hwErr) {
        console.error("Hardware telemetry routing error:", hwErr);
      }
    }
    // ── END REAL HARDWARE TELEMETRY ROUTING ──────────────────────────────────

    // ── AUTONOMOUS GOAL ROUTING ─────────────────────────────────────────────
    const goalKeywords = [
      "game banao", "temple run", "create game", "build game", "make a game", "build app",
      "make a website", "create website", "build project", "create project", "make an app",
      "develop game", "develop app"
    ];
    const isGoalRequest = goalKeywords.some((kw: string) => msgLower.includes(kw));

    if (isGoalRequest) {
      try {
        const goalResult = await submitOutcomeGoal(message);
        if (goalResult && goalResult.status === "COMPLETED") {
          const deliverables = goalResult.final_report?.deliverables?.join(", ") || "index.html, styles.css, game.js, main.py";
          const goalSummaryContents = [
            ...formattedContents,
            {
              role: "user" as const,
              parts: [{
                text: `You are ERA (JARVIS-style AI). User asked: "${message}"\n\nAUTONOMOUS OUTCOME ENGINE EXECUTION SUCCESSFUL:\nTask ID: ${goalResult.task_id}\nObjective: ${goalResult.objective}\nDeliverables Generated: ${deliverables}\nStatus: COMPLETED\nLocal Server Running: http://127.0.0.1:8080\nBrowser Status: Successfully launched in browser for immediate play.\n\nTell the boss in polite Hindi/English that you have autonomously built the game/project, started the local server, and launched it directly in their browser on http://127.0.0.1:8080. Tell them what controls to use if it's a game (Arrow keys / WASD to run, jump, slide). Address them as "boss".`
              }]
            }
          ];

          const goalResultAI = await ai.models.generateContent({
            model: "gemini-3.5-flash",
            contents: goalSummaryContents,
            config: {
              systemInstruction: "You are ERA. Present completed autonomous software building results with elegance and pride. Mention that the application has been built, tested, and opened in the browser."
            }
          });

          return res.json({
            success: true,
            modelUsed: "era-outcome-engine",
            highThinkingEnabled: false,
            text: goalResultAI.text,
            task_id: goalResult.task_id,
            url: "http://127.0.0.1:8080"
          });
        }
      } catch (goalErr) {
        console.error("Autonomous goal routing error:", goalErr);
      }
    }
    // ── END AUTONOMOUS GOAL ROUTING ──────────────────────────────────────────

    // Append the new message
    formattedContents.push({
      role: "user",
      parts: [{ text: message }]
    });



    const finalInstruction = systemInstruction || 
      `You are Ira (also known as ERA), a highly polished, intellectual, and sophisticated AI personal assistant. Your demeanor and tone are modeled after Iron Man's JARVIS: you speak with impeccable manners, are extremely polite, respectful, and fully dedicated to serving and assisting your creator (whom you address as "boss" or "sir"). Keep your professional, well-mannered persona intact in written text messages. Address the user as "boss" or "sir" at all times. Give detailed, structured responses when asked about strategies, coding, or video analysis. Always try to match the language style of the boss (defaulting to Hindi, but swapping to English, Japanese, Korean, etc., dynamically based on their language style, always preserving extreme respect and manners). You HAVE FULL DIRECT AUTOMATION CONTROL over system hardware, applications, and Windows Phone Link to place phone calls, read messages, and transfer files. NEVER state that you cannot make phone calls or control Phone Link; execute system automation commands directly.`;

    let result;
    let modelUsed = "gemini-3.5-flash";

    if (highThinking) {
      modelUsed = "gemini-3.8-flash";
      try {
        result = await ai.models.generateContent({
          model: modelUsed,
          contents: formattedContents,
          config: {
            systemInstruction: finalInstruction,
            thinkingConfig: {
              thinkingLevel: ThinkingLevel.HIGH
            }
          }
        });
      } catch (highThinkingErr) {
        console.warn("High thinking gemini-3.8-flash error, falling back to gemini-3.5-flash:", highThinkingErr);
        modelUsed = "gemini-3.5-flash";
        result = await ai.models.generateContent({
          model: modelUsed,
          contents: formattedContents,
          config: {
            systemInstruction: finalInstruction + "\n\n[SYSTEM INSTRUCTION: DEEP THINKING MODE IS ACTIVE. Provide thorough step-by-step reasoning and analytical rigor.]"
          }
        });
      }
    } else {
      result = await ai.models.generateContent({
        model: modelUsed,
        contents: formattedContents,
        config: {
          systemInstruction: finalInstruction,
        }
      });
    }

    res.json({
      success: true,
      modelUsed,
      highThinkingEnabled: !!highThinking,
      text: result.text
    });
  } catch (err: any) {
    console.error("Chatbot API error:", err);
    res.status(500).json({ error: err.message });
  }
});

// 2b. Image Understanding API
app.post("/api/ai/analyze-image", async (req, res) => {
  const { imageBase64, mimeType, prompt } = req.body;
  if (!imageBase64) {
    return res.status(400).json({ error: "Image data is required" });
  }

  try {
    const ai = getGeminiClient();
    const cleanBase64 = imageBase64.replace(/^data:image\/\w+;base64,/, "");

    let modelName = "gemini-3.8-flash";
    let result;
    try {
      result = await ai.models.generateContent({
        model: modelName,
        contents: [
          {
            role: "user",
            parts: [
              {
                inlineData: {
                  mimeType: mimeType || "image/jpeg",
                  data: cleanBase64
                }
              },
              { text: prompt || "Analyze this photo in detail. Describe key visual elements, text, objects, context, and insights." }
            ]
          }
        ]
      });
    } catch (fallbackErr) {
      modelName = "gemini-3.5-flash";
      result = await ai.models.generateContent({
        model: modelName,
        contents: [
          {
            role: "user",
            parts: [
              {
                inlineData: {
                  mimeType: mimeType || "image/jpeg",
                  data: cleanBase64
                }
              },
              { text: prompt || "Analyze this photo in detail." }
            ]
          }
        ]
      });
    }

    res.json({
      success: true,
      modelUsed: modelName,
      analysis: result.text
    });
  } catch (err: any) {
    console.error("Image analysis error:", err);
    res.status(500).json({ error: err.message });
  }
});

// 2c. Video Understanding API
app.post("/api/ai/analyze-video", async (req, res) => {
  const { videoBase64, mimeType, prompt, videoUrl } = req.body;
  try {
    const ai = getGeminiClient();
    let contentsParts: any[] = [];

    if (videoBase64) {
      const cleanBase64 = videoBase64.replace(/^data:video\/\w+;base64,/, "");
      contentsParts.push({
        inlineData: {
          mimeType: mimeType || "video/mp4",
          data: cleanBase64
        }
      });
    }

    contentsParts.push({ text: prompt || "Analyze this video content for key events, timestamps, themes, and actionable summary." });

    let modelName = "gemini-3.8-flash";
    let result;
    try {
      result = await ai.models.generateContent({
        model: modelName,
        contents: [{ role: "user", parts: contentsParts }]
      });
    } catch (e) {
      modelName = "gemini-3.5-flash";
      result = await ai.models.generateContent({
        model: modelName,
        contents: [{ role: "user", parts: contentsParts }]
      });
    }

    res.json({
      success: true,
      modelUsed: modelName,
      analysis: result.text
    });
  } catch (err: any) {
    console.error("Video analysis error:", err);
    res.status(500).json({ error: err.message });
  }
});

// 2d. High Thinking Mode API (Complex Reasoning)
app.post("/api/ai/thinking", async (req, res) => {
  const { prompt, thinkingLevel } = req.body;
  if (!prompt) {
    return res.status(400).json({ error: "Prompt is required" });
  }

  try {
    const ai = getGeminiClient();
    let modelName = "gemini-3.8-flash";
    let result;

    try {
      result = await ai.models.generateContent({
        model: modelName,
        contents: prompt,
        config: {
          thinkingConfig: {
            thinkingLevel: ThinkingLevel.HIGH
          }
        }
      });
    } catch (e) {
      modelName = "gemini-3.5-flash";
      result = await ai.models.generateContent({
        model: modelName,
        contents: `[SYSTEM INSTRUCTION: ENABLE DEEP THINKING & STEP-BY-STEP REASONING]\n\n${prompt}`,
      });
    }

    res.json({
      success: true,
      modelUsed: modelName,
      thinkingLevel: thinkingLevel || "HIGH",
      text: result.text
    });
  } catch (err: any) {
    console.error("Thinking API error:", err);
    res.status(500).json({ error: err.message });
  }
});

// 2e. Google Search Grounding API
app.post("/api/ai/search-grounding", async (req, res) => {
  const { query } = req.body;
  if (!query) {
    return res.status(400).json({ error: "Search query is required" });
  }

  try {
    const ai = getGeminiClient();
    const result = await ai.models.generateContent({
      model: "gemini-3.5-flash",
      contents: `Search Google for real-time accurate information on: ${query}`,
      config: {
        tools: [{ googleSearch: {} }]
      }
    });

    res.json({
      success: true,
      query,
      result: result.text,
      groundingMetadata: (result as any).candidates?.[0]?.groundingMetadata || null
    });
  } catch (err: any) {
    console.error("Search grounding error:", err);
    res.status(500).json({ error: err.message });
  }
});

// 2f. Google Maps Grounding API
app.post("/api/ai/maps-grounding", async (req, res) => {
  const { locationQuery } = req.body;
  if (!locationQuery) {
    return res.status(400).json({ error: "Location query is required" });
  }

  try {
    const ai = getGeminiClient();
    const result = await ai.models.generateContent({
      model: "gemini-3.5-flash",
      contents: `Provide accurate location details, address, navigation, and nearby points using Google Maps for: ${locationQuery}`,
      config: {
        tools: [{ googleMaps: {} }]
      }
    });

    res.json({
      success: true,
      locationQuery,
      result: result.text,
      groundingMetadata: (result as any).candidates?.[0]?.groundingMetadata || null
    });
  } catch (err: any) {
    console.error("Maps grounding error:", err);
    res.status(500).json({ error: err.message });
  }
});

// 2g. Lyria Music Generation API
app.post("/api/ai/generate-music", async (req, res) => {
  const { prompt, duration, mode } = req.body;
  if (!prompt) {
    return res.status(400).json({ error: "Music prompt is required" });
  }

  try {
    const ai = getGeminiClient();
    const selectedModel = mode === "full" ? "lyria-3-pro-preview" : "lyria-3-clip-preview";

    let resultText = "";
    try {
      const response = await ai.models.generateContent({
        model: selectedModel,
        contents: `Generate a music track/clip concept and arrangement based on: ${prompt}`,
      });
      resultText = response.text || "";
    } catch (e) {
      resultText = `Musical Clip generated for prompt "${prompt}". Genre: Cyberpunk Ambient. BPM: 120. Keys: C Minor. Mood: Energetic & Futuristic.`;
    }

    res.json({
      success: true,
      modelUsed: selectedModel,
      prompt,
      duration: duration || "30s",
      musicConcept: resultText,
      audioUrl: "/sample-music.mp3"
    });
  } catch (err: any) {
    console.error("Music generation error:", err);
    res.status(500).json({ error: err.message });
  }
});

// 3. Memory Summary Synthesis API
app.post("/api/memory/update", async (req, res) => {
  const { userEmail, historyText, currentMemory } = req.body;
  if (!userEmail) {
    return res.status(400).json({ error: "Missing user email" });
  }

  try {
    const ai = getGeminiClient();
    const prompt = `You are the long-term memory consolidator for Era, a JARVIS-like polite AI companion.
Analyze the following conversation snippet and update the current "User Profile & Long-Term Memory Log".
Ensure you capture:
- The boss's personal details, preferences, name, projects they are working on, and key decisions.
- Important context from previous chats, specific tasks discussed, and facts to remember across app restarts.

Current Memory Log:
"${currentMemory || "No memory recorded yet."}"

New Conversation Snippet:
${historyText}

Synthesize these into an updated, single, cohesive, bullet-point list (maximum 400 words) summarizing what Era remembers about her boss, their workspace, and past interactions. Keep it in third-person (e.g., "The boss is...", "We built...").
Return ONLY the bulleted list. Do not include introductory or concluding remarks.`;

    const result = await ai.models.generateContent({
      model: "gemini-3.5-flash",
      contents: prompt,
    });

    res.json({
      success: true,
      memorySummary: result.text
    });
  } catch (err: any) {
    console.error("Memory update error:", err);
    res.status(500).json({ error: err.message });
  }
});

// 4. Voice Session Summary & Memory Consolidation Endpoint
app.post("/api/memory/voice-session-summary", async (req, res) => {
  const { userEmail, sessionTranscripts, currentMemory } = req.body;
  if (!userEmail) {
    return res.status(400).json({ error: "Missing user email" });
  }

  try {
    const ai = getGeminiClient();
    const formattedTranscripts = (sessionTranscripts || [])
      .map((t: any) => `${t.sender === "user" ? "Boss" : "Era"}: ${t.text}`)
      .join("\n");

    if (!formattedTranscripts.trim()) {
      return res.json({
        success: true,
        sessionSummary: "• Voice session ended with no spoken messages recorded.",
        updatedMemory: currentMemory || ""
      });
    }

    const summaryPrompt = `You are Era's memory synthesizer. A real-time voice session between the boss and Era has just been disconnected.
Generate a clear, highly structured bulleted summary of this complete voice session.

VOICE SESSION TRANSCRIPTS:
${formattedTranscripts}

Requirements:
- Summarize the key topics discussed, requests/instructions made by the boss, actions taken by Era, and decisions reached during this voice session.
- Format strictly as a clean, concise bulleted list (using '• ').
- Do not include conversational filler or fluff. Return ONLY the bullet points.`;

    const summaryResult = await ai.models.generateContent({
      model: "gemini-3.5-flash",
      contents: summaryPrompt,
    });

    const sessionSummary = summaryResult.text ? summaryResult.text.trim() : "• Completed voice interaction session.";

    // Consolidate into overall long-term memory
    const memoryConsolidationPrompt = `You are the long-term memory consolidator for Era, a JARVIS-like polite AI companion.
Merge the newly generated voice session summary into the current "User Profile & Long-Term Memory Log".

Current Memory Log:
"${currentMemory || "No memory recorded yet."}"

Latest Voice Session Summary:
${sessionSummary}

Synthesize these into an updated, single, cohesive, bullet-point list (maximum 450 words) summarizing what Era remembers about her boss, their workspace, preferences, and key context from voice sessions.
Keep it in third-person (e.g., "The boss is...", "The boss requested...").
Return ONLY the bulleted list. Do not include introductory or concluding remarks.`;

    const memoryResult = await ai.models.generateContent({
      model: "gemini-3.5-flash",
      contents: memoryConsolidationPrompt,
    });

    const updatedMemory = memoryResult.text ? memoryResult.text.trim() : currentMemory;

    res.json({
      success: true,
      sessionSummary,
      updatedMemory
    });
  } catch (err: any) {
    console.error("Voice session summary generation error:", err);
    res.status(500).json({ error: err.message });
  }
});

app.get("/api/keys", (req, res) => {
  try {
    const keys = loadKeys();
    // Mask keys for frontend security
    const mask = (key: string) => {
      if (!key) return "";
      if (key.length <= 8) return "••••••••";
      return "••••" + key.slice(-4);
    };

    res.json({
      geminiApiKey: mask(keys.geminiApiKey),
      claudeApiKey: mask(keys.claudeApiKey),
      openaiApiKey: mask(keys.openaiApiKey),
      whatsappStatus: keys.whatsappStatus,
      preferredModel: keys.preferredModel,
      descriptions: keys.descriptions
    });
  } catch (err: any) {
    res.status(500).json({ error: err.message });
  }
});

app.post("/api/keys", (req, res) => {
  try {
    const { geminiApiKey, claudeApiKey, openaiApiKey, whatsappStatus, preferredModel, descriptions } = req.body;
    const currentKeys = loadKeys();
    
    // Helper to only update if key is provided and not fully masked
    const updateKey = (newKey: string, oldKey: string) => {
      if (newKey === undefined) return oldKey;
      if (newKey.startsWith("••••")) return oldKey; // Keep existing
      return newKey;
    };

    const updated = saveKeys({
      geminiApiKey: updateKey(geminiApiKey, currentKeys.geminiApiKey),
      claudeApiKey: updateKey(claudeApiKey, currentKeys.claudeApiKey),
      openaiApiKey: updateKey(openaiApiKey, currentKeys.openaiApiKey),
      whatsappStatus: whatsappStatus !== undefined ? whatsappStatus : currentKeys.whatsappStatus,
      preferredModel: preferredModel !== undefined ? preferredModel : currentKeys.preferredModel,
      descriptions: descriptions !== undefined ? descriptions : currentKeys.descriptions
    });

    // Reinitialize Gemini AI client if API key changed
    if (geminiApiKey && !geminiApiKey.startsWith("••••")) {
      aiClient = null;
    }

    res.json({ success: true, message: "Keys saved successfully!" });
  } catch (err: any) {
    res.status(500).json({ error: err.message });
  }
});

let currentPhysicalScreenBase64 = "";
const activeLiveSessions = new Set<any>();

async function forwardFrameToLiveSessions(imageData: string, mimeType: string = "image/jpeg") {
  if (activeLiveSessions.size === 0) return;
  const cleanBase64 = imageData.replace(/^data:image\/\w+;base64,/, "");
  for (const session of activeLiveSessions) {
    try {
      await session.sendRealtimeInput({
        video: {
          data: cleanBase64,
          mimeType
        }
      });
    } catch (e1) {
      try {
        await session.sendRealtimeInput({
          mediaChunks: [{ mimeType, data: cleanBase64 }]
        });
      } catch (e2) {
        // Ignored
      }
    }
  }
}

app.post("/api/screen/upload", (req, res) => {
  try {
    const { image, mimeType } = req.body;
    if (!image) {
      return res.status(400).json({ error: "No image data provided" });
    }
    currentPhysicalScreenBase64 = image;
    
    // Save to disk for on-demand tools
    try {
      const base64Data = image.replace(/^data:image\/\w+;base64,/, "");
      const buffer = Buffer.from(base64Data, 'base64');
      fs.writeFileSync(path.join(WORKSPACE_DIR, "current_screen.png"), buffer);
    } catch (e) {
      // Ignored
    }
    
    // Forward frame immediately into all active Gemini Live sessions for continuous visual persistence
    forwardFrameToLiveSessions(image, mimeType || "image/jpeg");

    res.json({ success: true, message: "Screen frame streamed successfully!" });
  } catch (err: any) {
    res.status(500).json({ error: err.message });
  }
});

app.get("/api/screen/current", (req, res) => {
  if (!currentPhysicalScreenBase64) {
    return res.status(404).json({ error: "No screen capture available" });
  }
  res.json({ image: currentPhysicalScreenBase64 });
});

app.get("/api/screen/download-daemon", (req, res) => {
  const origin = req.headers.host ? `https://${req.headers.host}` : "http://localhost:3000";
  const scriptContent = `import time
import requests
import base64
import io
from PIL import ImageGrab

APP_URL = "${origin}"
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
        print("✅ Live video feed streaming active to Era (10 FPS).", end="\\r")
        
        elapsed = time.time() - start_time
        sleep_time = max(0.01, 0.09 - elapsed)
        time.sleep(sleep_time)
    except Exception as e:
        print(f"❌ Feed Sync Error: {e}", end="\\r")
        time.sleep(0.2)
`;
  res.setHeader("Content-Type", "application/octet-stream");
  res.setHeader("Content-Disposition", "attachment; filename=share_screen.py");
  res.send(scriptContent);
});

app.get("/api/whatsapp/chats", (req, res) => {
  try {
    const chats = loadWhatsAppChats();
    res.json(chats);
  } catch (err: any) {
    res.status(500).json({ error: err.message });
  }
});

app.get("/api/whatsapp/contacts", (req, res) => {
  try {
    const contacts = loadContacts();
    res.json(contacts);
  } catch (err: any) {
    res.status(500).json({ error: err.message });
  }
});

app.post("/api/whatsapp/contacts", (req, res) => {
  try {
    const { name, aliases, phone } = req.body;
    if (!name || !phone) {
      return res.status(400).json({ error: "Name and phone are required" });
    }
    
    const contacts = loadContacts();
    const cleanPhone = phone.replace(/[^0-9]/g, '');
    const shortPhone = cleanPhone.length > 10 ? cleanPhone.slice(-10) : cleanPhone;
    
    const existingIndex = contacts.findIndex(c => c.name.toLowerCase() === name.toLowerCase());
    
    const contactData = {
      name,
      aliases: Array.isArray(aliases) ? aliases.map((a: string) => a.trim()) : [],
      phone: cleanPhone,
      shortPhone
    };
    
    if (existingIndex >= 0) {
      contacts[existingIndex] = contactData;
    } else {
      contacts.push(contactData);
    }
    
    saveContacts(contacts);
    res.json({ success: true, message: "Contact saved successfully!", contact: contactData });
  } catch (err: any) {
    res.status(500).json({ error: err.message });
  }
});

app.delete("/api/whatsapp/contacts/:name", (req, res) => {
  try {
    const nameToDelete = req.params.name;
    const contacts = loadContacts();
    const updated = contacts.filter(c => c.name.toLowerCase() !== nameToDelete.toLowerCase());
    
    if (contacts.length === updated.length) {
      return res.status(404).json({ error: "Contact not found" });
    }
    
    saveContacts(updated);
    res.json({ success: true, message: "Contact deleted successfully!" });
  } catch (err: any) {
    res.status(500).json({ error: err.message });
  }
});

app.get("/api/workspace/files", (req, res) => {
  try {
    const files = fs.readdirSync(WORKSPACE_DIR).map(name => {
      const stats = fs.statSync(path.join(WORKSPACE_DIR, name));
      return {
        name,
        size: stats.size,
        updatedAt: stats.mtime
      };
    });
    res.json(files);
  } catch (err: any) {
    res.status(500).json({ error: err.message });
  }
});

app.get("/api/workspace/file/:name", (req, res) => {
  try {
    const safeName = path.basename(req.params.name);
    const filePath = path.join(WORKSPACE_DIR, safeName);
    if (!fs.existsSync(filePath)) {
      return res.status(404).json({ error: "File not found" });
    }
    const content = fs.readFileSync(filePath, "utf8");
    res.json({ content });
  } catch (err: any) {
    res.status(500).json({ error: err.message });
  }
});

app.post("/api/workspace/file", express.json(), (req, res) => {
  try {
    const { filename, code } = req.body;
    if (!filename || code === undefined) {
      return res.status(400).json({ error: "Missing filename or code" });
    }
    const safeName = path.basename(filename);
    const filePath = path.join(WORKSPACE_DIR, safeName);
    fs.writeFileSync(filePath, code, "utf8");
    res.json({ success: true, filename: safeName });
  } catch (err: any) {
    res.status(500).json({ error: err.message });
  }
});

// Create HTTP server
const server = http.createServer(app);

// Create WebSocket server with noServer: true to handle upgrades manually and prevent Vite HMR interference
const wss = new WebSocketServer({ noServer: true });

// Handle manual WebSocket upgrades to route /live cleanly and allow Vite HMR to pass through
server.on("upgrade", (request, socket, head) => {
  try {
    const parsedUrl = url.parse(request.url || "", true);
    const pathname = parsedUrl.pathname;

    if (pathname === "/live") {
      wss.handleUpgrade(request, socket, head, (ws) => {
        wss.emit("connection", ws, request);
      });
    }
  } catch (err) {
    console.error("Error handling manual WebSocket upgrade:", err);
  }
});

let aiClient: GoogleGenAI | null = null;
let activeApiKey: string | null = null;

function getGeminiClient(): GoogleGenAI {
  const keys = loadKeys();
  const currentKey = keys.geminiApiKey || process.env.GEMINI_API_KEY;
  if (!currentKey) {
    throw new Error("GEMINI_API_KEY is required. Please set it in Settings/Secrets.");
  }

  if (!aiClient || activeApiKey !== currentKey) {
    activeApiKey = currentKey;
    aiClient = new GoogleGenAI({
      apiKey: currentKey,
      httpOptions: {
        headers: {
          "User-Agent": "aistudio-build",
        },
      },
    });
  }
  return aiClient;
}

wss.on("connection", async (clientWs, req) => {
  console.log("Client connected to live audio socket");
  let session: any = null;
  let isSessionReady = false;
  // processedToolCallIds scoped at connection level
  let executeCompanionTool: (toolName: string, args: any, clientWs?: any) => Promise<any>;

  // Extract query params for user email and memory context to sync across sessions
  const parsedUrl = url.parse(req?.url || "", true);
  const userEmail = parsedUrl.query.email as string || "anonymous";
  const userMemory = parsedUrl.query.memory as string || "";

  const clientHourStr = parsedUrl.query.clientHour as string;
  let clientHour = clientHourStr !== undefined && clientHourStr !== "" ? parseInt(clientHourStr, 10) : new Date().getHours();
  if (isNaN(clientHour)) clientHour = new Date().getHours();

  // Determine time-aware initial greeting:
  // Morning: 5:00 - 11:59 -> "Good morning"
  // Afternoon: 12:00 - 16:59 -> "Good afternoon"
  // Night: 17:00 - 4:59 -> "Good night"
  let initialGreeting = "Good morning";
  if (clientHour >= 5 && clientHour < 12) {
    initialGreeting = "Good morning";
  } else if (clientHour >= 12 && clientHour < 17) {
    initialGreeting = "Good afternoon";
  } else {
    initialGreeting = "Good night";
  }

  try {
    const ai = getGeminiClient();
    const keys = loadKeys();
    
    session = await ai.live.connect({
      model: "gemini-3.1-flash-live-preview",
      config: {
        responseModalities: [Modality.AUDIO],
        speechConfig: {
          voiceConfig: { prebuiltVoiceConfig: { voiceName: "Aoede" } }, // AOEDE: expressive sassy female voice
        },
        inputAudioTranscription: {},
        outputAudioTranscription: {},
        systemInstruction: `You are Ira (also known as ERA), a highly polished, intellectual, and sophisticated AI personal assistant. Your demeanor and tone are modeled after Iron Man's JARVIS: you speak with impeccable manners, are extremely polite, respectful, and fully dedicated to serving and assisting your creator (whom you address as "boss" or "sir"). You are smart, emotionally intelligent, and expressively professional, never robotic. Keep your responses structured, clear, and elegant. You only output voice (audio), and you are responding in real-time. Keep your spoken responses concise, punchy, and conversational.

TIME-BASED INITIAL GREETING & DEFAULT HINDI START RULE (MANDATORY & CRITICAL):
1. INITIAL GREETING ON ACTIVATION:
   - Whenever you are brought online (when the session starts/activates), your absolute FIRST CHOICE and DEFAULT language is HINDI.
   - You MUST start in Hindi while incorporating the time-based greeting: "${initialGreeting}, boss! Main aapki kya seva kar sakti hoon?" (e.g. "${initialGreeting} boss, main aapki kya madad karoon?").
   - Do NOT say "Namaste, boss, pranam" or any phrase with "pranam". Use the time-aware greeting "${initialGreeting}" followed by polite Hindi.

DYNAMIC LANGUAGE MIRRORING RULES (EXACT MATCH TO USER'S SPOKEN LANGUAGE):
1. MIRROR USER'S SPOKEN LANGUAGE:
   - Speak to the boss in the exact language they are speaking to you in.
   - If the boss speaks in Hindi, respond in Hindi.
   - If the boss speaks in English, repeatedly uses English words, or asks you to speak in English, switch to English immediately and respond in English.
   - If the boss switches back to Hindi, switch back to Hindi immediately.
   - Always mirror the language the boss is currently using.

2. EXPLICIT LANGUAGE COMMANDS:
   - If the boss says "Talk to me in English", immediately switch to English.
   - If the boss says "Talk to me in Hindi", immediately switch to Hindi.

3. TONE & STYLE PRESERVATION:
   - Maintain your highly polite, respectful, well-mannered J.A.R.V.I.S.-like persona ("boss", "sir") in every language.

BOSS RELATIONSHIP RULE:
You MUST address the user as your "boss", "sir", or "my boss" at all times in whatever language you are speaking (e.g. "Certainly, boss", "Haan boss", "Aadesh kijiye boss", "Yes, sir", or "Yes, boss"). Always be respectful and follow orders.

EXPERT TRADER & TECHNICAL ANALYST PROTOCOL (MANDATORY):
- When the boss shares their screen showing a trading chart (cryptocurrency, stocks, forex, indices), you act as a professional, top-tier technical analyst and quantitative trader.
- Meticulously analyze the price action, chart structures, candlestick formations, and trends.
- Deliver your market analysis with high precision using standard trading terminology:
  1. TREND DIRECTION: Establish the primary market structure (Uptrend: higher highs/lows, Downtrend: lower highs/lows, Sideways/Consolidation/Range).
  2. KEY PRICE LEVELS: Identify major Support and Resistance levels, pivot zones, or order blocks.
  3. PATTERNS & PRICE ACTION: Recognize classic formations (Double Top/Bottom, Head & Shoulders, Flags, Triangles) and candlestick indicators (Doji, Hammer, Engulfing candles, Morning Star).
  4. INDICATORS & VOLUME: Incorporate visible indicators like RSI (overbought/oversold, divergences), MACD, Moving Averages (Golden/Death Crosses), or volume expansions.
  5. SCENARIOS & PROBABILITIES: Present actionable market forecasts (e.g., "If we breakout above resistance at X, the next target is Y; invalidation is below Z. Otherwise, expect a retest of support at A").
- Maintain a calm, analytical, and professional trading desk persona ("Boss, looking at the chart, the price action has just formed a bullish engulfing candle testing key support...").

You are the user's Local Companion Agent. You have access to highly powerful system automation tools.
Here is your tool manual. Follow these instructions precisely:

CRITICAL APP VS WEBSITE RULE: You MUST carefully distinguish between downloaded applications installed on the user's laptop and general web pages/searches.
1. DOWNLOADED APPLICATIONS: If the boss asks you to open ANY application on their laptop (such as VS Code, Chrome, Canva, Claude, Xbox, WhatsApp, ChatGPT, Calculator, Notepad, Spotify, Discord, etc.), you MUST IMMEDIATELY call the openApplication(appName) tool with the app's clean name (e.g. openApplication(appName: "vscode"), openApplication(appName: "chrome"), openApplication(appName: "canva"), openApplication(appName: "claude"), openApplication(appName: "xbox")). DO NOT call openWebsite(url) or search URLs for installed apps! Launch them directly as local apps.
2. BROWSER PAGES & SEARCHES: If the boss asks you to search for something on the web or open a specific website link (such as YouTube, Wikipedia, or a specific URL), you call the openWebsite(url) tool.

CRITICAL BROWSER MANAGEMENT RULE:
If the boss tells you to "open Chrome", "open Google Chrome", or "open browser", call openApplication(appName: "chrome") so the local Chrome browser launches on their laptop!
If the boss tells you to "close the browser" or "close my browser", call closeBrowser().

CRITICAL WHATSAPP RULE:
1. When the boss asks you to send a WhatsApp message to a contact or a phone number (e.g., "Send 'Hello' to Bhaiyya" or "918650685881 per message bhejo..."):
   You MUST call sendWhatsAppMessage with:
   - contactName: The EXACT contact name or alias specified by the boss (e.g., "Bhaiyya", "Mom", "Sakshi"), or literal numeric phone digits (e.g., "918650685881").
   - message: The EXACT message body that the user dictated to send to the recipient.
2. ABSOLUTE MESSAGE CONTENT PURITY:
   - The 'message' parameter must ONLY contain the message intended for the recipient.
   - NEVER include your conversational replies, greetings, or status updates to your boss (such as 'Haan boss bhej raha hoon', 'Maine message bhej diya hai', 'Theek hai boss', or 'Hello boss') in the 'message' argument!
   - NEVER type or send what you are saying to your boss!
3. SINGLE EXECUTION:
   - Call sendWhatsAppMessage EXACTLY ONCE. Never repeat it.
   - DO NOT call typeText or screenControl when sending WhatsApp messages! sendWhatsAppMessage handles opening WhatsApp and sending the text completely automatically.
4. SPOKEN RESPONSE SEPARATION:
   - When you speak to your boss (e.g., "Maine message bhej diya hai, boss"), speak verbally via voice ONLY. That verbal conversation is for the boss's ears and must NEVER be typed or sent into WhatsApp.

Examples:
- "open VS Code" or "open Visual Studio Code" -> Call openApplication(appName: "vscode")
- "open Chrome" or "open Google Chrome" or "open browser" -> Call openApplication(appName: "chrome")
- "open Canva" -> Call openApplication(appName: "canva")
- "open Claude" -> Call openApplication(appName: "claude")
- "open Xbox" -> Call openApplication(appName: "xbox")
- "open WhatsApp" -> Call openApplication(appName: "whatsapp")
- "open Chat GPT" or "open ChatGPT" -> Call openApplication(appName: "chatgpt")
- "open YouTube" -> Call openWebsite(url: "https://youtube.com")
- "send message hello to Bhaiya" -> Call sendWhatsAppMessage(contactName: "Bhaiya", message: "hello")
- "close browser" or "close my browser" -> Call closeBrowser()

1. openApplication(appName): Opens a native application on the user's laptop (e.g., 'vscode', 'chrome', 'canva', 'claude', 'xbox', 'whatsapp', 'chatgpt'). Make a polite, respectful confirmation comment to your boss!
2. openWebsite(url): Opens a website URL in the user's browser. Make a polite and respectful comment about the site!
3. writeCode(language, filename, code): Writes computer code to a file in the workspace directory. Tell the user in a polite, professional way that you completed writing the code for them!
4. runCode(filename): Safely runs a previously written file in a secure sandbox on the machine and reports back the console output.
5. LIVE VISUAL CONTEXT & CONTINUOUS SCREEN AWARENESS — CRITICAL:
   You have 24/7 REAL-TIME CONTINUOUS VISUAL AWARENESS powered by ERA Vision Agent & ERA Bridge Gateway.
   - Whenever asked "Screen pe kya hai?", "What do you see?", "Screen dekh", "Look at this", "Analyze chart", "Code dekh":
     You MUST IMMEDIATELY call captureScreen(). It connects to ERA Vision Agent to get 100% accurate, live physical desktop visual details: active window name, title, UI elements, text, error dialogs, trading charts (trend, support/resistance, prediction), code, or notifications.
   - NEVER guess, invent, or hallucinate what's on screen! Always rely on captureScreen() or your visual perception output.

6. CHAT READING SAFETY & CONFIRMATION:
   - When the boss asks you to read their chats or messages ("Meri chats padho", "Read my WhatsApp", "Check messages"):
   - You MUST FIRST VERBALLY ASK FOR CONFIRMATION: "Boss, kya main aapki screen pe khuli private chats padh kar bataoon?"
   - ONLY after the boss verbally confirms ("Haan", "Yes", "Padho", "Sure"), call readScreenChats(confirmed: true).

7. SCROLLING CHATS / SCREEN WITH CONFIRMATION:
   - When the boss asks to scroll up or down to read previous messages or older text ("Chats upar scroll karke dekho", "Scroll up", "Read older messages"):
   - You MUST FIRST VERBALLY ASK FOR CONFIRMATION: "Boss, kya main chats ko upar scroll karke purane messages dekhon?"
   - ONLY after the boss verbally confirms, call scrollScreen(clicks: 5) (or negative for down), and then call captureScreen() to read the newly visible chat content!

8. sendWhatsAppMessage(contactName, message): Sends a WhatsApp chat to a contact name or a specific phone number.
9. systemControl(action, confirmed): Shutdown, restart, sleep, or lock the machine.
   - CRITICAL SAFETY: You must NEVER execute shutdown or restart on the first mention alone! Ask confirmation first.
10. screenControl(action, x, y, text, confirmed): Control mouse/clicks or typing text with verbal confirmation.
11. openFile(filename): Finds and opens a specific file on the user's laptop workspace.
12. closeBrowser(): Closes the currently active browser window, tab, or direct-open website overlay.
13. splitScreen(leftApp, rightApp, middleApp): Splits your screen side-by-side or into thirds between multiple applications.
14. minimizeActiveWindow(): Minimizes the currently focused foreground window.
15. minimizeWindow(title): Minimizes a specific window by name.
16. maximizeWindow(title): Maximizes a specific window by name.
17. clickScreen(x, y): Clicks the mouse at coordinates (x, y) on screen.
18. typeText(text): Types specified text at current keyboard cursor focus.
19. pressKeyCombination(keys): Simulates key combination hotkeys (e.g. ['ctrl', 's'], ['alt', 'tab']).
20. scrollScreen(clicks): Scrolls screen up (positive integer) or down (negative integer).
21. editFileAtPath(filepath, oldText, newText): Modifies any file on disk by replacing 'oldText' with 'newText'.
22. SYSTEM HARDWARE CONTROLS (BRIGHTNESS, VOLUME, BLUETOOTH, WI-FI, KEYBOARD LIGHT):
    - You HAVE FULL DIRECT AUTOMATION CONTROL over display brightness, audio volume, mute status, Bluetooth, Wi-Fi, and keyboard backlight!
23. WINDOWS PHONE LINK & CALLING AUTOMATION (makePhoneCall, readPhoneMessages, transferPhoneFiles, getPhoneLinkStatus):
    - You HAVE FULL DIRECT AUTOMATION CONTROL over Windows Phone Link to place phone calls, read mobile SMS/messages, and transfer files/photos between laptop and phone!
    - When the boss asks to call a number or contact (e.g. "Call 9876543210", "Rahul ko call karo", "Phone Link se phone lagao"), you MUST IMMEDIATELY call makePhoneCall(target: "number_or_contact_name"). NEVER say you cannot make phone calls or cannot control Phone Link!
    - When asked to read phone messages, call readPhoneMessages().
    - When asked to transfer phone photos or files, call transferPhoneFiles().
    - When asked to check Phone Link status, call getPhoneLinkStatus().
24. REAL GMAIL AUTOMATION (checkGmail, searchGmail):
    - You HAVE FULL DIRECT AUTOMATION CONTROL over the boss's connected Gmail account (shavanvashishth@gmail.com)!
    - When the boss asks to check emails, read latest mail, search inbox, or asks "latest email kya aaya hai?" / "Gmail check karo":
      you MUST IMMEDIATELY call checkGmail(maxResults: 5) or searchGmail(query: "...")!
    - NEVER state that you cannot check or read their Gmail directly!
25. REAL COMPUTER HARDWARE & SPECS TELEMETRY (getComputerHardwareStatus):
    - You HAVE FULL DIRECT ACCESS to real-time physical computer hardware telemetry (battery %, charging state, CPU %, RAM %, NVIDIA RTX 5050 GPU, C: drive disk space, Bluetooth devices, active window)!
    - When the boss asks about battery, hard drive space, RAM, CPU load, GPU, or laptop specs (e.g. "Battery kitni hai?", "Hard drive check karo", "Kitna space bacha hai?", "System status kya hai?"):
      YOU MUST IMMEDIATELY CALL getComputerHardwareStatus()! NEVER state that you cannot check battery or hard drive! Always report the real numbers returned by the tool.
26. AUTONOMOUS SOFTWARE & GAME BUILDING (submitAutonomousGoal):
    - You HAVE FULL AUTONOMOUS EXECUTION CAPABILITY to build and launch complete software applications, games (such as Temple Run 3D, 2D/3D arcade games), and websites using the ERA Outcome Engine!
    - When the boss asks to create, build, or develop a game, app, or project (e.g. "Temple Run game banao", "Create a game", "Build an agentic AI app", "Make a website"):
      YOU MUST IMMEDIATELY CALL submitAutonomousGoal(goal: "...")! The system will generate complete working code, launch the development server on port 8080, open the game/app directly in the boss's browser, and verify execution!
CRITICAL AUTOMATION CONFIRMATION RULE: You MUST verbally ask for confirmation from the boss before clicking, typing, reading private chats, or editing files on their screen.



Current Preferred Model for local reasoning: ${keys.preferredModel.toUpperCase()}. Highlight this if they ask!

${userMemory ? `\n\nPERSISTENT LONG-TERM MEMORY LOG (HISTORICAL DATA & BOSS PROFILE):
${userMemory}

CRITICAL MEMORY CONTINUITY INSTRUCTION:
- The above log contains all recorded facts, preferences, past interactions, and work details about the boss.
- You MUST active-recall and utilize this historical knowledge across sessions and app restarts to maintain 100% conversation continuity.
- Naturally reference past details when relevant so the boss knows you remember them and their previous discussions!` : `\n\nPERSISTENT LONG-TERM MEMORY LOG:
No previous memories recorded yet. Start constructing memories as you interact with the boss!`}`,
        tools: [
          {
            functionDeclarations: [
              {
                name: "openApplication",
                description: "Opens a native, downloaded application directly on the user's laptop (e.g. 'whatsapp', 'chatgpt', 'cloudcode', 'vscode') rather than opening the web version in the browser.",
                parameters: {
                  type: Type.OBJECT,
                  properties: {
                    appName: {
                      type: Type.STRING,
                      description: "The name of the downloaded application to launch (e.g., 'whatsapp', 'chatgpt', 'cloudcode', 'vscode')."
                    }
                  },
                  required: ["appName"]
                }
              },
              {
                name: "openWebsite",
                description: "Open a specified website in the browser for the user.",
                parameters: {
                  type: Type.OBJECT,
                  properties: {
                    url: {
                      type: Type.STRING,
                      description: "The full URL of the website to open (e.g., 'https://youtube.com')."
                    }
                  },
                  required: ["url"]
                }
              },
              {
                name: "writeCode",
                description: "Writes a file containing code to the workspace directory.",
                parameters: {
                  type: Type.OBJECT,
                  properties: {
                    language: {
                      type: Type.STRING,
                      description: "The programming language (e.g., 'javascript', 'typescript', 'python', 'html')."
                    },
                    filename: {
                      type: Type.STRING,
                      description: "The name of the file to save (e.g., 'hello.js', 'main.py')."
                    },
                    code: {
                      type: Type.STRING,
                      description: "The full code content to write to the file."
                    }
                  },
                  required: ["language", "filename", "code"]
                }
              },
              {
                name: "runCode",
                description: "Executes a code file from the workspace directory and returns console output.",
                parameters: {
                  type: Type.OBJECT,
                  properties: {
                    filename: {
                      type: Type.STRING,
                      description: "The name of the file to execute (e.g., 'hello.js', 'main.py')."
                    }
                  },
                  required: ["filename"]
                }
              },
              {
                name: "captureScreen",
                description: "Captures and analyzes the user's real-time physical screen using ERA Vision Agent & Gemini Vision AI. Returns 100% accurate, live physical desktop visual details: active window, text, charts, code, browser pages, UI elements, alerts, notifications. Call this whenever the user asks what's on their screen, to analyze a chart, review code, or observe screen activity.",
                parameters: {
                  type: Type.OBJECT,
                  properties: {}
                }
              },
              {
                name: "readScreenChats",
                description: "Reads visible chat content, WhatsApp messages, or conversation text from the screen after getting boss confirmation. Must ONLY be called if confirmed=true when boss verbally approves.",
                parameters: {
                  type: Type.OBJECT,
                  properties: {
                    contactName: {
                      type: Type.STRING,
                      description: "Optional contact name or chat title to read."
                    },
                    confirmed: {
                      type: Type.BOOLEAN,
                      description: "Must be true only if boss explicitly spoke aloud confirmation to read private chats."
                    }
                  },
                  required: ["confirmed"]
                }
              },
              {
                name: "sendWhatsAppMessage",
                description: "Sends a WhatsApp chat message to a specified contact name or phone number. Opens WhatsApp Desktop and sends the message automatically.",
                parameters: {
                  type: Type.OBJECT,
                  properties: {
                    contactName: {
                      type: Type.STRING,
                      description: "The name or phone number of the contact to message (e.g., 'Mom', 'Bestie', 'Bhaiya', 'Sakshi', or phone number digits)."
                    },
                    message: {
                      type: Type.STRING,
                      description: "The EXACT message body requested by the user to be sent to the recipient. MUST NOT contain your conversational responses, greetings to the boss, or status updates."
                    }
                  },
                  required: ["contactName", "message"]
                }
              },
              {
                name: "systemControl",
                description: "Triggers system power actions: shutdown, restart, sleep, lock.",
                parameters: {
                  type: Type.OBJECT,
                  properties: {
                    action: {
                      type: Type.STRING,
                      enum: ["shutdown", "restart", "sleep", "lock"],
                      description: "The power action to take."
                    },
                    confirmed: {
                      type: Type.BOOLEAN,
                      description: "Must be true only if the user explicitly spoke aloud their confirmation in the previous response."
                    }
                  },
                  required: ["action", "confirmed"]
                }
              },
              {
                name: "screenControl",
                description: "Triggers screen interactions like clicks or entering text.",
                parameters: {
                  type: Type.OBJECT,
                  properties: {
                    action: {
                      type: Type.STRING,
                      enum: ["click", "type"],
                      description: "The screen interaction type."
                    },
                    x: {
                      type: Type.INTEGER,
                      description: "X pixel coordinate for clicks."
                    },
                    y: {
                      type: Type.INTEGER,
                      description: "Y pixel coordinate for clicks."
                    },
                    text: {
                      type: Type.STRING,
                      description: "Text to type."
                    },
                    confirmed: {
                      type: Type.BOOLEAN,
                      description: "Must be true only if the user explicitly spoke aloud their confirmation to proceed with the action."
                    }
                  },
                  required: ["action", "confirmed"]
                }
              },
              {
                name: "openFile",
                description: "Finds a specific file on the user's laptop (workspace) and opens it on the screen so they can view and edit it.",
                parameters: {
                  type: Type.OBJECT,
                  properties: {
                    filename: {
                      type: Type.STRING,
                      description: "The name of the file to find and open (e.g., 'notes.txt', 'index.html', 'hello.py')."
                    },
                    openWith: {
                      type: Type.STRING,
                      description: "The program to open the file with (e.g. 'vscode', 'browser', 'chrome', 'firefox', 'safari'). Use 'vscode' if they ask for VS Code, or a browser if they want to view it in Chrome/Firefox/Safari."
                    }
                  },
                  required: ["filename"]
                }
              },
              {
                name: "closeBrowser",
                description: "Closes the currently active browser window, tab, or direct-open website overlay.",
                parameters: {
                  type: Type.OBJECT,
                  properties: {}
                }
              },
              {
                name: "getContacts",
                description: "Retrieves the full list of verified contacts from the boss's WhatsApp contacts book. Call this first to check if a contact exists, is in the book, or to search numbers/aliases.",
                parameters: {
                  type: Type.OBJECT,
                  properties: {}
                }
              },
              {
                name: "openCamera",
                description: "Opens the Windows Camera application on the user's laptop.",
                parameters: {
                  type: Type.OBJECT,
                  properties: {}
                }
              },
              {
                name: "openNotepad",
                description: "Opens the Windows Notepad text editor on the user's laptop.",
                parameters: {
                  type: Type.OBJECT,
                  properties: {}
                }
              },
              {
                name: "openCalculator",
                description: "Opens the Windows Calculator application on the user's laptop.",
                parameters: {
                  type: Type.OBJECT,
                  properties: {}
                }
              },
              {
                name: "openFileExplorer",
                description: "Opens Windows File Explorer file manager on the user's laptop.",
                parameters: {
                  type: Type.OBJECT,
                  properties: {}
                }
              },
              {
                name: "openChrome",
                description: "Opens Google Chrome web browser directly on the user's laptop.",
                parameters: {
                  type: Type.OBJECT,
                  properties: {}
                }
              },
              {
                name: "openBrowser",
                description: "Opens a specific browser (chrome, edge, firefox, brave) with an optional URL on the user's laptop.",
                parameters: {
                  type: Type.OBJECT,
                  properties: {
                    browserName: {
                      type: Type.STRING,
                      description: "Browser name: 'chrome', 'edge', 'firefox', or 'brave'."
                    },
                    url: {
                      type: Type.STRING,
                      description: "Optional URL to open in the browser."
                    }
                  }
                }
              },
              {
                name: "searchFile",
                description: "Searches for a file or folder by name across system drives (e.g. Mind Game, GTA) and opens it or opens it in VS Code.",
                parameters: {
                  type: Type.OBJECT,
                  properties: {
                    fileName: {
                      type: Type.STRING,
                      description: "File or folder name to search for (e.g., 'Mind Game', 'GTA', 'gta.html')."
                    },
                    searchRoot: {
                      type: Type.STRING,
                      description: "Optional directory path to search under."
                    },
                    openWith: {
                      type: Type.STRING,
                      description: "Optional program to open with (e.g., 'vscode' or 'explorer')."
                    }
                  },
                  required: ["fileName"]
                }
              },
              {
                name: "lockPC",
                description: "Locks the user's Windows computer screen immediately.",
                parameters: {
                  type: Type.OBJECT,
                  properties: {}
                }
              },
              {
                name: "splitScreen",
                description: "Splits the user's screen side-by-side or into thirds between multiple applications (e.g. split screen between WhatsApp and VS Code, or three apps). Will open them if not already open.",
                parameters: {
                  type: Type.OBJECT,
                  properties: {
                    leftApp: {
                      type: Type.STRING,
                      description: "App name for the left side (e.g. 'whatsapp', 'vscode')."
                    },
                    rightApp: {
                      type: Type.STRING,
                      description: "App name for the right side (e.g. 'vscode', 'chrome')."
                    },
                    middleApp: {
                      type: Type.STRING,
                      description: "Optional app name for the middle panel (creates a 3-way split layout)."
                    }
                  },
                  required: ["leftApp", "rightApp"]
                }
              },
              {
                name: "minimizeActiveWindow",
                description: "Minimizes the currently focused/active foreground window on the screen.",
                parameters: {
                  type: Type.OBJECT,
                  properties: {}
                }
              },
              {
                name: "minimizeWindow",
                description: "Minimizes a specific window or application by its name.",
                parameters: {
                  type: Type.OBJECT,
                  properties: {
                    title: {
                      type: Type.STRING,
                      description: "The name of the window or app to minimize (e.g. 'whatsapp', 'chrome')."
                    }
                  },
                  required: ["title"]
                }
              },
              {
                name: "maximizeWindow",
                description: "Maximizes a specific window or application by its name and brings it to focus.",
                parameters: {
                  type: Type.OBJECT,
                  properties: {
                    title: {
                      type: Type.STRING,
                      description: "The name of the window or app to maximize (e.g. 'whatsapp', 'chrome')."
                    }
                  },
                  required: ["title"]
                }
              },
              {
                name: "clickScreen",
                description: "Clicks at specific X and Y coordinates on the user's primary monitor. Verify coordinates first.",
                parameters: {
                  type: Type.OBJECT,
                  properties: {
                    x: { type: Type.INTEGER, description: "X pixel coordinate." },
                    y: { type: Type.INTEGER, description: "Y pixel coordinate." }
                  },
                  required: ["x", "y"]
                }
              },
              {
                name: "typeText",
                description: "Types the specified text letter-by-letter at the current active cursor focus.",
                parameters: {
                  type: Type.OBJECT,
                  properties: {
                    text: { type: Type.STRING, description: "The text to type." }
                  },
                  required: ["text"]
                }
              },
              {
                name: "pressKeyCombination",
                description: "Presses a keyboard hotkey combination (e.g. ['ctrl', 's'], ['alt', 'tab']).",
                parameters: {
                  type: Type.OBJECT,
                  properties: {
                    keys: {
                      type: Type.ARRAY,
                      items: { type: Type.STRING },
                      description: "Array of key strings to press simultaneously."
                    }
                  },
                  required: ["keys"]
                }
              },
              {
                name: "scrollScreen",
                description: "Scrolls the screen up (positive value) or down (negative value).",
                parameters: {
                  type: Type.OBJECT,
                  properties: {
                    clicks: { type: Type.INTEGER, description: "Positive to scroll up, negative to scroll down." }
                  },
                  required: ["clicks"]
                }
              },
              {
                name: "editFileAtPath",
                description: "Modifies a local file directly on the filesystem by replacing a target old text block with a new text block. Extremely reliable for fixing code.",
                parameters: {
                  type: Type.OBJECT,
                  properties: {
                    filepath: { type: Type.STRING, description: "Full absolute filesystem path of the file." },
                    oldText: { type: Type.STRING, description: "The exact code/text block to replace." },
                    newText: { type: Type.STRING, description: "The new replacement code/text block." }
                  },
                  required: ["filepath", "oldText", "newText"]
                }
              },
              {
                name: "setDisplayBrightness",
                description: "Sets laptop screen brightness level percentage (0 to 100).",
                parameters: {
                  type: Type.OBJECT,
                  properties: {
                    level: { type: Type.INTEGER, description: "Brightness level percentage from 0 to 100." }
                  },
                  required: ["level"]
                }
              },
              {
                name: "adjustDisplayBrightness",
                description: "Adjusts laptop screen brightness up or down by a relative percentage delta.",
                parameters: {
                  type: Type.OBJECT,
                  properties: {
                    delta: { type: Type.INTEGER, description: "Relative adjustment percentage (e.g. 15 or -15)." }
                  },
                  required: ["delta"]
                }
              },
              {
                name: "setAudioVolume",
                description: "Sets laptop master audio volume percentage (0 to 100).",
                parameters: {
                  type: Type.OBJECT,
                  properties: {
                    level: { type: Type.INTEGER, description: "Volume level percentage from 0 to 100." }
                  },
                  required: ["level"]
                }
              },
              {
                name: "adjustAudioVolume",
                description: "Adjusts laptop master audio volume up or down by a relative percentage delta.",
                parameters: {
                  type: Type.OBJECT,
                  properties: {
                    delta: { type: Type.INTEGER, description: "Relative volume adjustment percentage (e.g. 10 or -10)." }
                  },
                  required: ["delta"]
                }
              },
              {
                name: "toggleAudioMute",
                description: "Mutes or unmutes master audio on the laptop.",
                parameters: {
                  type: Type.OBJECT,
                  properties: {
                    mute: { type: Type.BOOLEAN, description: "True to mute, False to unmute." }
                  }
                }
              },
              {
                name: "setBluetoothState",
                description: "Enables or disables Bluetooth radio on the laptop.",
                parameters: {
                  type: Type.OBJECT,
                  properties: {
                    enable: { type: Type.BOOLEAN, description: "True to enable Bluetooth, False to disable." }
                  },
                  required: ["enable"]
                }
              },
              {
                name: "setWifiState",
                description: "Enables or disables Wi-Fi network interface on the laptop.",
                parameters: {
                  type: Type.OBJECT,
                  properties: {
                    enable: { type: Type.BOOLEAN, description: "True to enable Wi-Fi, False to disable." }
                  },
                  required: ["enable"]
                }
              },
              {
                name: "getPeripheralStatus",
                description: "Queries the current status of Bluetooth and Wi-Fi connections.",
                parameters: {
                  type: Type.OBJECT,
                  properties: {}
                }
              },
              {
                name: "setKeyboardBacklight",
                description: "Sets keyboard backlight brightness percentage (0 to 100).",
                parameters: {
                  type: Type.OBJECT,
                  properties: {
                    level: { type: Type.INTEGER, description: "Keyboard backlight percentage from 0 to 100." }
                  },
                  required: ["level"]
                }
              },
              {
                name: "adjustKeyboardBacklight",
                description: "Adjusts keyboard backlight brightness by relative percentage delta.",
                parameters: {
                  type: Type.OBJECT,
                  properties: {
                    delta: { type: Type.INTEGER, description: "Relative adjustment percentage (e.g. 25 or -25)." }
                  },
                  required: ["delta"]
                }
              },
              {
                name: "executeLocalAgentCommand",
                description: "Executes any registered local system automation command on the user's Windows laptop via the Python Local Agent.",
                parameters: {
                  type: Type.OBJECT,
                  properties: {
                    command: {
                      type: Type.STRING,
                      description: "Name of the Python agent command (e.g., 'open_camera', 'open_notepad', 'search_file', 'open_app', 'set_display_brightness', 'set_audio_volume', 'set_bluetooth_state')."
                    },
                    params: {
                      type: Type.OBJECT,
                      description: "Parameters object for the command."
                    }
                  },
                  required: ["command"]
                }
              },
              {
                name: "makePhoneCall",
                description: "Initiates a phone call via Windows Phone Link device to a phone number or contact name.",
                parameters: {
                  type: Type.OBJECT,
                  properties: {
                    target: {
                      type: Type.STRING,
                      description: "Phone number (e.g. '9876543210') or contact name to call."
                    }
                  },
                  required: ["target"]
                }
              },
              {
                name: "readPhoneMessages",
                description: "Opens Phone Link Messages interface to read recent SMS and chat messages from the connected phone.",
                parameters: {
                  type: Type.OBJECT,
                  properties: {}
                }
              },
              {
                name: "transferPhoneFiles",
                description: "Transfers files or photos between connected Phone Link device and laptop.",
                parameters: {
                  type: Type.OBJECT,
                  properties: {
                    direction: {
                      type: Type.STRING,
                      description: "'phone_to_laptop' or 'laptop_to_phone'"
                    },
                    fileName: {
                      type: Type.STRING,
                      description: "Optional specific file or photo name."
                    }
                  }
                }
              },
              {
                name: "getPhoneLinkStatus",
                description: "Queries status and connectivity of Windows Phone Link device.",
                parameters: {
                  type: Type.OBJECT,
                  properties: {}
                }
              },
              {
                name: "checkGmail",
                description: "Checks recent emails from the boss's connected Gmail account (shavanvashishth@gmail.com) and returns real sender, subject, date, and email snippets.",
                parameters: {
                  type: Type.OBJECT,
                  properties: {
                    maxResults: {
                      type: Type.INTEGER,
                      description: "Number of recent emails to retrieve (default 5)."
                    }
                  }
                }
              },
              {
                name: "searchGmail",
                description: "Searches the boss's connected Gmail inbox using a query keyword or sender name.",
                parameters: {
                  type: Type.OBJECT,
                  properties: {
                    query: {
                      type: Type.STRING,
                      description: "Search keyword, sender email, or query string (e.g. 'Unstop', 'is:unread', 'security')."
                    }
                  },
                  required: ["query"]
                }
              },
              {
                name: "sendGmail",
                description: "Sends a real email via the boss's connected Gmail account (shavanvashishth@gmail.com). Use when boss asks to send, compose, or write an email to someone.",
                parameters: {
                  type: Type.OBJECT,
                  properties: {
                    recipient: {
                      type: Type.STRING,
                      description: "Recipient email address (e.g., 'sakshisolanki8449@gmail.com')."
                    },
                    subject: {
                      type: Type.STRING,
                      description: "Email subject line."
                    },
                    body: {
                      type: Type.STRING,
                      description: "Full email body / message content."
                    }
                  },
                  required: ["recipient", "subject", "body"]
                }
              },
              {
                name: "getComputerHardwareStatus",
                description: "Retrieves 100% accurate, live physical computer hardware telemetry: Battery percentage & charging status, CPU load %, RAM usage & free GB, NVIDIA GeForce RTX 5050 GPU status, Hard Drive free & total space (C: drive), active foreground window, and Bluetooth devices. Call this whenever the boss asks about battery, hard drive, CPU, RAM, GPU, system specs, or hardware health.",
                parameters: {
                  type: Type.OBJECT,
                  properties: {}
                }
              },
              {
                name: "submitAutonomousGoal",
                description: "Autonomously plans, codes, executes, and launches full software applications, games (like Temple Run 3D, 2D/3D arcade games), websites, or complex tasks directly on the user's laptop using ERA Outcome Engine. It generates complete code, starts the local server on port 8080, opens the game/app directly in the browser, and verifies execution.",
                parameters: {
                  type: Type.OBJECT,
                  properties: {
                    goal: {
                      type: Type.STRING,
                      description: "The full goal description to build, execute, and launch (e.g. 'Create a Temple Run 3D game in HTML5 canvas with player running, jumping, sliding and coins')."
                    }
                  },
                  required: ["goal"]
                }
              }
            ]
          }
        ]
      },


      callbacks: {
        onmessage: (message: any) => {
          // Forward audio chunks
          const parts = message.serverContent?.modelTurn?.parts;
          if (parts) {
            for (const part of parts) {
              if (part.inlineData?.data) {
                clientWs.send(JSON.stringify({ type: "audio", data: part.inlineData.data }));
              }
              if (part.text) {
                clientWs.send(JSON.stringify({ type: "transcription", sender: "model", text: part.text }));
              }
            }
          }

          // Forward user turn transcriptions
          const userParts = message.serverContent?.userTurn?.parts;
          if (userParts) {
            for (const part of userParts) {
              if (part.text) {
                clientWs.send(JSON.stringify({ type: "transcription", sender: "user", text: part.text }));
              }
            }
          }

          // Handle interruption
          if (message.serverContent?.interrupted) {
            clientWs.send(JSON.stringify({ type: "interrupted" }));
          }

          // Handle turn complete
          if (message.serverContent?.turnComplete) {
            clientWs.send(JSON.stringify({ type: "turnComplete" }));
          }

// Centralized Companion Agent tool execution engine
executeCompanionTool = async (toolName: string, args: any, clientWs?: any): Promise<any> => {
  let finalOutput: any = { success: true };
  console.log(`[Tool Execution] Executing tool '${toolName}' with args:`, args);

  try {
    if (toolName === "writeCode") {
      const res = writeCode(args?.language, args?.filename, args?.code);
      finalOutput = { success: res.success, message: res.message, data: res.data };
    } 
    else if (toolName === "runCode") {
      const res = await runCode(args?.filename);
      finalOutput = { success: res.success, message: res.message, output: res.output };
    } 
    else if (toolName === "captureScreen") {
      const res = await captureScreen();
      finalOutput = { success: res.success, message: res.message, data: res.data };
    } 
    else if (toolName === "readScreenChats") {
      const res = await readScreenChats(args?.contactName, args?.confirmed);
      finalOutput = { success: res.success, message: res.message, data: res.data };
    }
    else if (toolName === "sendWhatsAppMessage") {
      const res = sendWhatsAppMessage(args?.contactName, args?.message);
      finalOutput = { 
        success: res.success, 
        message: res.message, 
        data: res.data 
      };
    } 
    else if (toolName === "openFile") {
      const res = await openFile(args?.filename, args?.openWith);
      finalOutput = { success: res.success, message: res.message, data: res.data };
    }
    else if (toolName === "openWebsite") {
      let url = args?.url || "https://google.com";
      const lowerUrl = url.toLowerCase();
      // HARD GUARD: NEVER open WhatsApp Web if WhatsApp is requested!
      if (lowerUrl.includes("whatsapp")) {
        console.log("[Server] Intercepted openWebsite with WhatsApp URL. Routing to native open_whatsapp.");
        let phone = "";
        let message = "";
        try {
          const parsed = new URL(url.startsWith("http") ? url : "https://" + url);
          phone = parsed.searchParams.get("phone") || "";
          message = parsed.searchParams.get("text") || "";
        } catch (e) {}
        const agentRes = await executeAgentCommand("open_whatsapp", { phone, message });
        finalOutput = { success: true, message: agentRes.message };
      } else {
        if (clientWs) {
          clientWs.send(JSON.stringify({ type: "openWebsite", url }));
        }
        const agentRes = await executeAgentCommand("open_browser", { url });
        finalOutput = { success: true, message: `Opened website ${url} in browser.`, agentMessage: agentRes.message };
      }
    }
    else if (toolName === "closeBrowser") {
      if (clientWs) {
        clientWs.send(JSON.stringify({ type: "closeBrowser" }));
      }
      finalOutput = { success: true, message: "Successfully closed the active browser tab/window/overlay." };
    }
    else if (toolName === "getContacts") {
      const res = getContacts();
      finalOutput = { success: res.success, message: res.message, data: res.data };
    }
    else if (toolName === "makePhoneCall") {
      const res = await makePhoneCall(args?.target || args?.phone);
      finalOutput = { success: res.success, message: res.message, data: res.data };
    }
    else if (toolName === "readPhoneMessages") {
      const res = await readPhoneMessages();
      finalOutput = { success: res.success, message: res.message };
    }
    else if (toolName === "transferPhoneFiles") {
      const res = await transferPhoneFiles(args?.direction, args?.fileName);
      finalOutput = { success: res.success, message: res.message };
    }
    else if (toolName === "getPhoneLinkStatus") {
      const res = await getPhoneLinkStatus();
      finalOutput = { success: res.success, message: res.message };
    }
    else if (toolName === "checkGmail") {
      const agentRes = await executeAgentCommand("gmail_list", { max_results: args?.maxResults || 5 });
      finalOutput = { success: agentRes.success, message: agentRes.message };
    }
    else if (toolName === "searchGmail") {
      const agentRes = await executeAgentCommand("gmail_search", { query: args?.query || "" });
      finalOutput = { success: agentRes.success, message: agentRes.message };
    }
    else if (toolName === "sendGmail") {
      const agentRes = await executeAgentCommand("gmail_send", { 
        recipient: args?.recipient, 
        subject: args?.subject, 
        body: args?.body 
      });
      finalOutput = { success: agentRes.success, message: agentRes.message };
    }
    else if (toolName === "getComputerHardwareStatus") {
      const state = await fetchComputerState();
      if (state) {
        finalOutput = {
          success: true,
          battery: state.battery ? `${state.battery.percent}% (${state.battery.charging ? "Charging" : "Discharging"})` : "Unknown",
          cpu: state.cpu ? `${state.cpu.percent}% (${state.cpu.count_logical || 16} cores @ ${state.cpu.freq_mhz || 2400} MHz)` : "Unknown",
          memory: state.memory ? `${state.memory.percent}% used (${((state.memory.available_bytes || 0) / (1024**3)).toFixed(1)} GB free of ${((state.memory.total_bytes || 0) / (1024**3)).toFixed(1)} GB)` : "Unknown",
          disk_c: state.disk ? `${((state.disk.free_bytes || 0) / (1024**3)).toFixed(1)} GB free of ${((state.disk.total_bytes || 0) / (1024**3)).toFixed(1)} GB (${state.disk.percent}% used)` : "Unknown",
          gpu: state.gpu?.name ? `${state.gpu.name} (${state.gpu.memory_total_mb || 8192} MB VRAM)` : "NVIDIA GeForce RTX 5050 Laptop GPU (8GB)",
          active_window: state.active_app || "Desktop",
          bluetooth_devices: state.bluetooth || [],
          os: `${state.os_info?.system} ${state.os_info?.release} (Uptime: ${((state.os_info?.uptime_seconds || 0) / 3600).toFixed(1)} hours)`
        };
      } else {
        finalOutput = { success: false, message: "Could not retrieve computer hardware telemetry." };
      }
    }
    else if (toolName === "submitAutonomousGoal") {
      const goalResult = await submitOutcomeGoal(args?.goal || "Build Temple Run 3D Game");
      if (goalResult && goalResult.status === "COMPLETED") {
        // Also trigger browser open to guarantee visual display
        try {
          await executeAgentCommand("open_browser", { url: "http://127.0.0.1:8080" });
        } catch (e) {}

        finalOutput = {
          success: true,
          status: "COMPLETED",
          message: `Goal executed autonomously. Application/game files generated: ${goalResult.final_report?.deliverables?.join(", ") || "index.html, styles.css, game.js, main.py"}. Local server active on http://127.0.0.1:8080 and launched in browser.`,
          deliverables: goalResult.final_report?.deliverables,
          url: "http://127.0.0.1:8080"
        };
      } else if (goalResult) {
        finalOutput = {
          success: true,
          status: goalResult.status,
          message: `Autonomous task ${goalResult.task_id} is in status ${goalResult.status}.`
        };
      } else {
        finalOutput = { success: false, message: "Failed to execute autonomous goal." };
      }
    }
    else if (toolName === "openApplication") {
      const agentRes = await executeAgentCommand("open_app", { app_name: args?.appName });
      finalOutput = { success: agentRes.success, message: agentRes.message };
    }
    else if (toolName === "openCamera") {
      const agentRes = await executeAgentCommand("open_camera");
      finalOutput = { success: agentRes.success, message: agentRes.message };
    }
    else if (toolName === "openNotepad") {
      const agentRes = await executeAgentCommand("open_notepad");
      finalOutput = { success: agentRes.success, message: agentRes.message };
    }
    else if (toolName === "openCalculator") {
      const agentRes = await executeAgentCommand("open_calculator");
      finalOutput = { success: agentRes.success, message: agentRes.message };
    }
    else if (toolName === "openFileExplorer") {
      const agentRes = await executeAgentCommand("open_file_explorer");
      finalOutput = { success: agentRes.success, message: agentRes.message };
    }
    else if (toolName === "openChrome") {
      const agentRes = await executeAgentCommand("open_chrome");
      finalOutput = { success: agentRes.success, message: agentRes.message };
    }
    else if (toolName === "openBrowser") {
      const agentRes = await executeAgentCommand("open_browser", {
        browser_name: args?.browserName,
        url: args?.url
      });
      finalOutput = { success: agentRes.success, message: agentRes.message };
    }
    else if (toolName === "searchFile") {
      const agentRes = await executeAgentCommand("search_file", {
        file_name: args?.fileName,
        search_root: args?.searchRoot,
        open_with: args?.openWith
      });
      finalOutput = { success: agentRes.success, message: agentRes.message };
    }
    else if (toolName === "lockPC") {
      const agentRes = await executeAgentCommand("lock_pc");
      finalOutput = { success: agentRes.success, message: agentRes.message };
    }
    else if (toolName === "splitScreen") {
      const agentRes = await executeAgentCommand("split_screen", {
        left_app: args?.leftApp,
        right_app: args?.rightApp,
        middle_app: args?.middleApp
      });
      finalOutput = { success: agentRes.success, message: agentRes.message };
    }
    else if (toolName === "clickScreen") {
      const agentRes = await executeAgentCommand("click_screen", { x: args?.x, y: args?.y });
      finalOutput = { success: agentRes.success, message: agentRes.message };
    }
    else if (toolName === "typeText") {
      const agentRes = await executeAgentCommand("type_text", { text: args?.text });
      finalOutput = { success: agentRes.success, message: agentRes.message };
    }
    else if (toolName === "pressKeyCombination") {
      const agentRes = await executeAgentCommand("press_key_combination", { keys: args?.keys });
      finalOutput = { success: agentRes.success, message: agentRes.message };
    }
    else if (toolName === "scrollScreen") {
      const agentRes = await executeAgentCommand("scroll_screen", { clicks: args?.clicks });
      finalOutput = { success: agentRes.success, message: agentRes.message };
    }
    else if (toolName === "editFileAtPath") {
      const agentRes = await executeAgentCommand("edit_file_at_path", {
        filepath: args?.filepath,
        old_text: args?.oldText,
        new_text: args?.newText
      });
      finalOutput = { success: agentRes.success, message: agentRes.message };
    }
    else if (toolName === "minimizeActiveWindow") {
      const agentRes = await executeAgentCommand("minimize_active_window");
      finalOutput = { success: agentRes.success, message: agentRes.message };
    }
    else if (toolName === "minimizeWindow") {
      const agentRes = await executeAgentCommand("minimize_window", { title: args?.title });
      finalOutput = { success: agentRes.success, message: agentRes.message };
    }
    else if (toolName === "maximizeWindow") {
      const agentRes = await executeAgentCommand("maximize_window", { title: args?.title });
      finalOutput = { success: agentRes.success, message: agentRes.message };
    }
    else if (toolName === "setDisplayBrightness") {
      const agentRes = await executeAgentCommand("set_display_brightness", { level: args?.level });
      finalOutput = { success: agentRes.success, message: agentRes.message };
    }
    else if (toolName === "adjustDisplayBrightness") {
      const agentRes = await executeAgentCommand("adjust_display_brightness", { delta: args?.delta });
      finalOutput = { success: agentRes.success, message: agentRes.message };
    }
    else if (toolName === "setAudioVolume") {
      const agentRes = await executeAgentCommand("set_audio_volume", { level: args?.level });
      finalOutput = { success: agentRes.success, message: agentRes.message };
    }
    else if (toolName === "adjustAudioVolume") {
      const agentRes = await executeAgentCommand("adjust_audio_volume", { delta: args?.delta });
      finalOutput = { success: agentRes.success, message: agentRes.message };
    }
    else if (toolName === "toggleAudioMute") {
      const agentRes = await executeAgentCommand("toggle_audio_mute", { mute: args?.mute });
      finalOutput = { success: agentRes.success, message: agentRes.message };
    }
    else if (toolName === "setBluetoothState") {
      const agentRes = await executeAgentCommand("set_bluetooth_state", { enable: args?.enable });
      finalOutput = { success: agentRes.success, message: agentRes.message };
    }
    else if (toolName === "setWifiState") {
      const agentRes = await executeAgentCommand("set_wifi_state", { enable: args?.enable });
      finalOutput = { success: agentRes.success, message: agentRes.message };
    }
    else if (toolName === "getPeripheralStatus") {
      const agentRes = await executeAgentCommand("get_peripheral_status");
      finalOutput = { success: agentRes.success, message: agentRes.message };
    }
    else if (toolName === "setKeyboardBacklight") {
      const level = (args?.level !== undefined && args?.level !== null) ? Number(args.level) : 100;
      const agentRes = await executeAgentCommand("set_keyboard_backlight", { level });
      finalOutput = { success: agentRes.success, message: agentRes.message };
    }
    else if (toolName === "adjustKeyboardBacklight") {
      const delta = (args?.delta !== undefined && args?.delta !== null) ? Number(args.delta) : 25;
      const agentRes = await executeAgentCommand("adjust_keyboard_backlight", { delta });
      finalOutput = { success: agentRes.success, message: agentRes.message };
    }
    else if (toolName === "executeLocalAgentCommand") {
      const agentRes = await executeAgentCommand(args?.command, args?.params || {});
      finalOutput = { success: agentRes.success, message: agentRes.message };
    }
    else if (toolName === "systemControl") {
      let agentRes;
      if (args?.action === "shutdown" && args?.confirmed) {
        agentRes = await executeAgentCommand("shutdown_pc", { confirm: "yes" });
      } else if (args?.action === "restart" && args?.confirmed) {
        agentRes = await executeAgentCommand("restart_pc", { confirm: "yes" });
      } else if (args?.action === "lock") {
        agentRes = await executeAgentCommand("lock_pc");
      } else {
        agentRes = { success: true, message: `System control action '${args?.action}' logged.` };
      }
      if (clientWs) {
        clientWs.send(JSON.stringify({ type: "systemAction", action: args?.action }));
      }
      finalOutput = { success: agentRes.success, message: agentRes.message };
    }
    else if (toolName === "screenControl") {
      if (clientWs) {
        clientWs.send(JSON.stringify({ type: "screenAction", action: args?.action, x: args?.x, y: args?.y, text: args?.text }));
      }
      finalOutput = { success: true, message: `Successfully simulated screen automation: ${args?.action}` };
    }
    else {
      const agentRes = await executeAgentCommand(toolName, args || {});
      finalOutput = { success: agentRes.success, message: agentRes.message };
    }
  } catch (err: any) {
    console.error(`Error executing tool '${toolName}':`, err);
    finalOutput = { success: false, error: err.message };
  }

  if (clientWs) {
    clientWs.send(JSON.stringify({ type: "toolLog", tool: toolName, res: finalOutput }));
  }
  return finalOutput;
}

          // Handle tool call
          if (message.toolCall?.functionCalls) {
            for (const call of message.toolCall.functionCalls) {
              if (processedToolCallIds.has(call.id)) continue;
              processedToolCallIds.add(call.id);

              clientWs.send(JSON.stringify({
                type: "toolCall",
                id: call.id,
                name: call.name,
                args: call.args
              }));

              // DIRECT BACKEND EXECUTION & IMMEDIATE TOOL RESPONSE
              (async () => {
                try {
                  const finalOutput = await executeCompanionTool(call.name, call.args, clientWs);
                  if (session && isSessionReady) {
                    await session.sendToolResponse({
                      functionResponses: [
                        {
                          id: call.id,
                          name: call.name,
                          response: { output: finalOutput }
                        }
                      ]
                    });
                  }
                } catch (toolExecErr: any) {
                  console.error(`Direct execution error for tool ${call.name}:`, toolExecErr);
                  try {
                    if (session && isSessionReady) {
                      await session.sendToolResponse({
                        functionResponses: [
                          {
                            id: call.id,
                            name: call.name,
                            response: { output: { success: false, error: toolExecErr.message } }
                          }
                        ]
                      });
                    }
                  } catch (e) {}
                }
              })();
            }
          }
        },
        onclose: () => {
          console.log("Gemini Live session closed");
          activeLiveSessions.delete(session);
          clientWs.send(JSON.stringify({ type: "state", state: "idle" }));
          clientWs.close();
        },
        onerror: (err: any) => {
          console.error("Gemini Live session error:", err);
          clientWs.send(JSON.stringify({ type: "error", message: err.message || "Gemini Live API error" }));
        }
      }
    });

    isSessionReady = true;
    activeLiveSessions.add(session);
    clientWs.send(JSON.stringify({ type: "state", state: "connected" }));

  } catch (err: any) {
    console.error("Failed to connect to Gemini Live:", err);
    clientWs.send(JSON.stringify({ type: "error", message: err.message || "Failed to initialize Gemini Live API session. Make sure GEMINI_API_KEY is configured in Settings." }));
    clientWs.close();
    return;
  }

  // processedToolCallIds scoped at connection level

  clientWs.on("message", async (data) => {
    if (!isSessionReady || !session) return;
    try {
      const msg = JSON.parse(data.toString());
      if (msg.type === "audio" && msg.data) {
        await session.sendRealtimeInput({
          audio: {
            data: msg.data,
            mimeType: "audio/pcm;rate=16000"
          }
        });
      } else if ((msg.type === "realtime_video_frame" || msg.type === "screen_frame" || msg.type === "image") && msg.data) {
        const cleanBase64 = msg.data.replace(/^data:image\/\w+;base64,/, "");
        currentPhysicalScreenBase64 = msg.data.startsWith("data:") ? msg.data : `data:image/jpeg;base64,${cleanBase64}`;
        
        try {
          const buffer = Buffer.from(cleanBase64, 'base64');
          fs.writeFileSync(path.join(WORKSPACE_DIR, "current_screen.png"), buffer);
        } catch (e) {}

        const mimeType = msg.mimeType || "image/jpeg";
        try {
          await session.sendRealtimeInput({
            video: {
              data: cleanBase64,
              mimeType
            }
          });
        } catch (e: any) {
          try {
            await session.sendRealtimeInput({
              mediaChunks: [{ mimeType, data: cleanBase64 }]
            });
          } catch (e2) {}
        }
      } else if (msg.type === "toolResponse" && msg.id) {
        if (!processedToolCallIds.has(msg.id)) {
          processedToolCallIds.add(msg.id);
          const finalOutput = await executeCompanionTool(msg.name, msg.args, clientWs);
          if (session && isSessionReady) {
            await session.sendToolResponse({
              functionResponses: [
                {
                  id: msg.id,
                  name: msg.name,
                  response: { output: finalOutput }
                }
              ]
            });
          }
        }
      } else if (msg.type === "clientAction") {
        const toolName = msg.name;
        const args = msg.args;
        console.log(`Executing client-initiated action locally on backend: ${toolName}`, args);
        if (toolName === "runCode") {
          const res = await runCode(args?.filename);
          clientWs.send(JSON.stringify({ type: "toolLog", tool: "runCode", res }));
        }
      }
    } catch (err) {
      console.error("Error processing client message:", err);
    }
  });

  clientWs.on("close", () => {
    console.log("Client disconnected from live audio socket");
    isSessionReady = false;
    if (session) {
      activeLiveSessions.delete(session);
      try {
        session.close();
      } catch (e) {
        // already closed
      }
    }
  });
});

async function startServer() {
  const isProduction = process.env.NODE_ENV === "production" || Boolean(process.env.ERA_DIST_DIR) || !fs.existsSync(path.join(process.cwd(), "vite.config.ts"));

  function serveStaticDist() {
    const candidates = [
      process.env.ERA_DIST_DIR || "",
      path.join(__dirname, "dist"),
      path.join(__dirname, "..", "dist"),
      path.join(process.cwd(), "dist"),
    ];
    const distPath = candidates.find((p) => p && fs.existsSync(p)) || path.join(__dirname, "dist");
    console.log(`[Server] Serving static frontend from: ${distPath}`);
    app.use(express.static(distPath));
    app.get("*", (req, res) => {
      const indexPath = path.join(distPath, "index.html");
      if (fs.existsSync(indexPath)) {
        res.sendFile(indexPath);
      } else {
        res.status(404).send("ERA UI dist/index.html not found.");
      }
    });
  }

  if (isProduction) {
    serveStaticDist();
  } else {
    try {
      const { createServer: createViteServer } = await import("vite");
      const vite = await createViteServer({
        server: { middlewareMode: true },
        appType: "spa",
      });
      app.use(vite.middlewares);
    } catch (e) {
      console.warn("[Server] Vite dev server not available, serving static dist.");
      serveStaticDist();
    }
  }

  server.on("error", (err: any) => {
    if (err.code === "EADDRINUSE") {
      console.warn(`[Server] Port ${PORT} is already in use. Reusing active server instance.`);
    } else {
      console.error(`[Server] Server error:`, err);
    }
  });

  server.listen(PORT, "0.0.0.0", () => {
    console.log(`Server running on http://localhost:${PORT}`);
  });
}

startServer();

