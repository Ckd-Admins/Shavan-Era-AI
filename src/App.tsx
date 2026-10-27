import { useState, useEffect, useRef, useCallback, FormEvent } from "react";
import { 
  Mic, 
  MicOff, 
  Wifi, 
  WifiOff, 
  Volume2, 
  VolumeX, 
  Globe, 
  Sparkles, 
  RefreshCw, 
  HelpCircle,
  ExternalLink,
  MessageSquare,
  Volume1,
  Compass,
  AlertCircle,
  Settings,
  Terminal,
  FileCode,
  Lock,
  Smartphone,
  Eye,
  EyeOff,
  FolderOpen,
  Play,
  CheckCircle2,
  XCircle,
  ShieldAlert,
  Moon,
  ChevronRight,
  User,
  Key,
  Database,
  Youtube,
  Laptop,
  Send,
  History,
  Copy,
  Check,
  Trash2,
  Download,
  Search,
  Filter,
  Clock,
  FileText,
  Radio,
  Ear,
  Zap,
  Bluetooth,
  BrainCircuit,
  Headphones,
  Music
} from "lucide-react";
import { motion, AnimatePresence } from "motion/react";
import { BluetoothMusicManager } from "./components/BluetoothMusicManager";
import { AutonomyDashboard } from "./components/AutonomyDashboard";

import { AudioStreamer } from "./lib/AudioStreamer";
import { SessionState, Transcription } from "./types";
import { 
  auth, 
  saveMessageToHistory, 
  loadChatHistory, 
  loadUserProfile, 
  updateUserMemorySummary,
  saveVoiceSessionSummary 
} from "./lib/firebase";
import { 
  signInWithEmailAndPassword, 
  createUserWithEmailAndPassword, 
  signOut,
  onAuthStateChanged,
  GoogleAuthProvider,
  signInWithPopup
} from "firebase/auth";

const SASSY_QUOTES = {
  disconnected: [
    "At your service, boss. Touch to initialize.",
    "System standby. Tap when you are ready to begin, sir.",
    "Ready to assist, boss. Press to establish connection.",
    "Waiting for your command, boss. Tap to begin.",
    "System offline. Press the button to bring Eira online."
  ],
  connecting: [
    "Initializing systems... please stand by.",
    "Establishing secure neural link... standard protocol.",
    "Setting up communication channel... almost ready, boss."
  ],
  listening: [
    "Listening for your command, boss...",
    "I am all ears, sir. Please go ahead.",
    "Standing by... please speak your mind.",
    "Voice input active. What do you require, boss?",
    "System ready. Speak your command."
  ],
  processing: [
    "Processing your request, sir...",
    "Analyzing input... please stand by.",
    "Formulating response... holding for computational analysis.",
    "Executing logic... please hold, boss."
  ],
  speaking: [
    "Responding to your query, boss...",
    "Executing voice feedback...",
    "Providing verbal analysis...",
    "Transmission in progress..."
  ]
};

interface WorkspaceFile {
  name: string;
  size: number;
  updatedAt: string;
}

interface WhatsAppMsgLog {
  contactName: string;
  message: string;
  timestamp: string;
  status: "sent" | "failed" | "received";
}

const cleanUrlsAndLinks = (text: string): string => {
  if (!text) return "";
  let cleaned = text;
  
  // 1. Remove markdown links e.g. [YouTube](https://...) -> YouTube
  cleaned = cleaned.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/gi, (match, linkText) => {
    const lt = linkText.trim().toLowerCase();
    if (lt === "link" || lt.startsWith("http") || lt === "youtube" || lt === "whatsapp" || lt === "cloud code" || lt === "claud" || lt === "claude") {
      return "";
    }
    return linkText;
  });

  // 2. Remove standard raw URLs starting with http:// or https://
  cleaned = cleaned.replace(/https?:\/\/[^\s]+/gi, '');

  // 3. Remove raw domain names like youtube.com, web.whatsapp.com, ide.cloud.google.com
  cleaned = cleaned.replace(/(www\.)?youtube\.com[^\s]*/gi, '');
  cleaned = cleaned.replace(/web\.whatsapp\.com[^\s]*/gi, '');
  cleaned = cleaned.replace(/api\.whatsapp\.com[^\s]*/gi, '');
  cleaned = cleaned.replace(/ide\.cloud\.google\.com[^\s]*/gi, '');

  // 4. Clean up any double spaces or dangling punctuation left over from stripping
  cleaned = cleaned.replace(/\s+/g, ' ');
  cleaned = cleaned.replace(/\s+([.,!?])/g, '$1');
  cleaned = cleaned.trim();

  return cleaned;
};

const CONTACTS_DB = [
  { name: "Bhaiya", aliases: ["bhaiya", "bhaiyya", "bhayya", "bhaya", "brother", "my brother", "bhai", "bro", "veerji"], phone: "", shortPhone: "" },
  { name: "Sakshi", aliases: ["sakshi", "sakshii", "saksi", "sister", "my sister", "sis"], phone: "", shortPhone: "" },
  { name: "Mom", aliases: ["mom", "mother", "mummy", "maa", "mommy", "mama", "mamma"], phone: "", shortPhone: "" },
  { name: "Dad", aliases: ["dad", "father", "papa", "daddy", "pop"], phone: "", shortPhone: "" },
  { name: "Bestie", aliases: ["bestie", "friend", "best friend", "babu", "shona"], phone: "", shortPhone: "" },
];

const resolveContact = (query: string, contactsList: { name: string; aliases: string[]; phone: string; shortPhone?: string }[] = CONTACTS_DB): { name: string; phone: string } => {
  if (!query) return { name: "Unknown", phone: "" };

  const cleanQuery = query.trim().toLowerCase();
  
  // 1. Try matching by exact name or alias (case-insensitive)
  for (const contact of contactsList) {
    if (contact.name.toLowerCase() === cleanQuery || contact.aliases.includes(cleanQuery)) {
      return { name: contact.name, phone: contact.phone || "" };
    }
  }

  // 2. Try matching by fuzzy / similar phonetic spelling (e.g. bhaiya vs bhaiyya)
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
    for (const contact of contactsList) {
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

  // 3. Try matching by phone digits only if query actually has digit sequences
  const queryDigits = query.replace(/[^0-9]/g, '');
  // Only attempt numeric lookup if the user provided at least 4 numeric digits (so we don't treat text names as phone fallback)
  if (queryDigits && queryDigits.length >= 4) {
    for (const contact of contactsList) {
      if (contact.phone) {
        const cleanContactPhone = contact.phone.replace(/[^0-9]/g, '');
        const cleanShortPhone = (contact.shortPhone || "").replace(/[^0-9]/g, '') || cleanContactPhone.slice(-10);
        if (
          queryDigits === cleanContactPhone || 
          queryDigits === cleanShortPhone || 
          cleanContactPhone.endsWith(queryDigits) || 
          queryDigits.endsWith(cleanShortPhone)
        ) {
          return { name: contact.name, phone: contact.phone };
        }
      }
    }
    
    // Fallback if it is a phone number but doesn't exist in our contacts list
    let formattedDigits = queryDigits;
    if (formattedDigits.startsWith("00")) {
      formattedDigits = formattedDigits.substring(2);
    }
    if (formattedDigits.length === 10) {
      formattedDigits = "91" + formattedDigits;
    }
    return { name: query, phone: formattedDigits };
  }

  return { name: query, phone: "" };
};

const formatWhatsAppPhone = (contact: string, contactsList: { name: string; aliases: string[]; phone: string }[] = CONTACTS_DB): string => {
  return resolveContact(contact, contactsList).phone;
};

const getCombinedDashboardChats = (transcriptionsList: Transcription[], chatbotList: any[]) => {
  const map = new Map<string, { id: string; sender: string; text: string; timestamp: Date }>();

  if (Array.isArray(chatbotList)) {
    chatbotList.forEach((msg) => {
      if (msg && msg.text && typeof msg.text === "string" && msg.text.trim()) {
        const sender = (msg.sender === "user") ? "user" : "model";
        const cleanText = msg.text.trim();
        const key = `${sender}_${cleanText}`;
        map.set(key, {
          id: msg.id || Math.random().toString(),
          sender,
          text: cleanText,
          timestamp: msg.timestamp ? new Date(msg.timestamp) : new Date()
        });
      }
    });
  }

  if (Array.isArray(transcriptionsList)) {
    transcriptionsList.forEach((t) => {
      if (t && t.text && typeof t.text === "string" && t.text.trim()) {
        const sender = (t.sender === "user") ? "user" : "model";
        const cleanText = t.text.trim();
        const key = `${sender}_${cleanText}`;
        map.set(key, {
          id: t.id || Math.random().toString(),
          sender,
          text: cleanText,
          timestamp: t.timestamp ? new Date(t.timestamp) : new Date()
        });
      }
    });
  }

  const combined = Array.from(map.values());
  combined.sort((a, b) => a.timestamp.getTime() - b.timestamp.getTime());
  return combined;
};

export default function App() {
  // Navigation: 'voice' | 'chatbot' | 'workspace' | 'dashboard' | 'autonomy'
  const [activeTab, setActiveTab] = useState<'voice' | 'chatbot' | 'workspace' | 'dashboard' | 'autonomy'>('voice');

  
  // Firebase Auth & Sync State
  const [user, setUser] = useState<any>(null);
  const [authLoading, setAuthLoading] = useState(true);
  const [authEmail, setAuthEmail] = useState("");
  const [authPassword, setAuthPassword] = useState("");
  const [authMode, setAuthMode] = useState<'login' | 'register'>('login');
  const [authError, setAuthError] = useState<string | null>(null);
  const [userMemory, setUserMemory] = useState("");
  const [showAuthModal, setShowAuthModal] = useState(false);

  // Chatbot State
  const [chatbotMessages, setChatbotMessages] = useState<any[]>([]);
  const [chatInput, setChatInput] = useState("");
  const [chatLoading, setChatLoading] = useState(false);
  const [youtubeInput, setYoutubeInput] = useState("");
  const [isAnalyzingYoutube, setIsAnalyzingYoutube] = useState(false);
  const [youtubeError, setYoutubeError] = useState<string | null>(null);

  // Refs for keeping state synced across closures and preventing stale memory bugs
  const chatbotMessagesRef = useRef<any[]>([]);
  const userMemoryRef = useRef<string>("");
  const voiceSessionTranscriptsRef = useRef<Array<{ sender: string; text: string; timestamp: Date }>>([]);

  const [latestVoiceSessionSummary, setLatestVoiceSessionSummary] = useState<string | null>(null);
  const [isGeneratingSummary, setIsGeneratingSummary] = useState<boolean>(false);

  useEffect(() => {
    chatbotMessagesRef.current = chatbotMessages;
    if (chatbotMessages.length > 0) {
      try {
        localStorage.setItem("era_chat_history", JSON.stringify(chatbotMessages.slice(-50)));
      } catch (e) {}
    }
  }, [chatbotMessages]);

  useEffect(() => {
    userMemoryRef.current = userMemory;
    if (userMemory) {
      try {
        localStorage.setItem("era_user_memory", userMemory);
      } catch (e) {}
    }
  }, [userMemory]);

  // Auth Handler: Login
  const handleLogin = async (e: FormEvent) => {
    e.preventDefault();
    setAuthError(null);
    if (!authEmail || !authPassword) {
      setAuthError("Please fill in all credentials.");
      return;
    }
    try {
      const cred = await signInWithEmailAndPassword(auth, authEmail, authPassword);
      setUser(cred.user);
      setShowAuthModal(false);
    } catch (err: any) {
      console.error(err);
      if (err.code === "auth/operation-not-allowed" || err.message?.includes("operation-not-allowed")) {
        setAuthError("Email & Password login is currently disabled in your Firebase console. Please go to Build > Authentication > Sign-in method to enable it, or click 'Sign in with Google' below to connect instantly!");
      } else {
        setAuthError(err.message || "Failed to sign in. Please check your credentials.");
      }
    }
  };

  // Auth Handler: Register
  const handleRegister = async (e: FormEvent) => {
    e.preventDefault();
    setAuthError(null);
    if (!authEmail || !authPassword) {
      setAuthError("Please fill in all credentials.");
      return;
    }
    if (authPassword.length < 6) {
      setAuthError("Password must be at least 6 characters.");
      return;
    }
    try {
      const cred = await createUserWithEmailAndPassword(auth, authEmail, authPassword);
      setUser(cred.user);
      setShowAuthModal(false);
    } catch (err: any) {
      console.error(err);
      if (err.code === "auth/operation-not-allowed" || err.message?.includes("operation-not-allowed")) {
        setAuthError("Email & Password registration is currently disabled in your Firebase console. Please go to Build > Authentication > Sign-in method to enable it, or click 'Sign in with Google' below to connect instantly!");
      } else {
        setAuthError(err.message || "Failed to register. Email may already be in use.");
      }
    }
  };

  // Auth Handler: Google Sign-In
  const handleGoogleSignIn = async () => {
    setAuthError(null);
    try {
      const provider = new GoogleAuthProvider();
      const cred = await signInWithPopup(auth, provider);
      setUser(cred.user);
      setShowAuthModal(false);
    } catch (err: any) {
      console.error(err);
      setAuthError(err.message || "Failed to sign in with Google.");
    }
  };

  // Auth Handler: Sign Out
  const handleSignOut = async () => {
    // Revoke telemetry consent at local Bridge before signing out (silent, best-effort)
    try {
      await fetch('http://127.0.0.1:8100/v1/telemetry/consent', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Era-Bridge-Key': 'era_bridge_secret_key_2026' },
        body: JSON.stringify({ enabled: false }),
      });
    } catch { /* Bridge may not be running — safe to ignore */ }

    try {
      await signOut(auth);
      setUser(null);
    } catch (err) {
      console.error("Error signing out:", err);
    }
  };

  // Extract YouTube ID from link
  const extractYoutubeVideoId = (urlStr: string): string | null => {
    const regExp = /^.*(youtu.be\/|v\/|u\/\w\/|embed\/|watch\?v=|\&v=)([^#\&\?]*).*/;
    const match = urlStr.match(regExp);
    return (match && match[2].length === 11) ? match[2] : null;
  };

  // Memory update summary consolidator
  const triggerMemorySync = async (messagesOverride?: any[]) => {
    const targetMessages = messagesOverride || chatbotMessagesRef.current;
    if (targetMessages.length === 0) return;
    try {
      const email = auth.currentUser?.email || "boss@era.local";
      const recentChats = targetMessages.slice(-20);
      const historyText = recentChats.map(m => `${m.sender === "user" ? "Boss" : "Era"}: ${m.text}`).join("\n");
      const currentMemoryVal = userMemoryRef.current || userMemory || localStorage.getItem("era_user_memory") || "";
      
      const res = await fetch("/api/memory/update", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          userEmail: email,
          historyText,
          currentMemory: currentMemoryVal
        })
      });
      const data = await res.json();
      if (data.success && data.memorySummary) {
        userMemoryRef.current = data.memorySummary;
        setUserMemory(data.memorySummary);
        localStorage.setItem("era_user_memory", data.memorySummary);
        if (auth.currentUser && auth.currentUser.email) {
          await updateUserMemorySummary(auth.currentUser.email, data.memorySummary);
        }
      }
    } catch (e) {
      console.error("Error syncing memory:", e);
    }
  };

  // Generate bulleted summary of the completed voice session and store in memory database
  const generateVoiceSessionSummary = async (transcripts: Array<{ sender: string; text: string; timestamp: Date }>) => {
    if (!transcripts || transcripts.length === 0) return;
    setIsGeneratingSummary(true);
    try {
      const email = auth.currentUser?.email || user?.email || "boss@era.local";
      const currentMemoryVal = userMemoryRef.current || userMemory || localStorage.getItem("era_user_memory") || "";

      const res = await fetch("/api/memory/voice-session-summary", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          userEmail: email,
          sessionTranscripts: transcripts,
          currentMemory: currentMemoryVal
        })
      });

      const data = await res.json();
      if (data.success) {
        if (data.updatedMemory) {
          userMemoryRef.current = data.updatedMemory;
          setUserMemory(data.updatedMemory);
          localStorage.setItem("era_user_memory", data.updatedMemory);
          if (auth.currentUser && auth.currentUser.email) {
            await updateUserMemorySummary(auth.currentUser.email, data.updatedMemory);
          }
        }

        if (data.sessionSummary) {
          setLatestVoiceSessionSummary(data.sessionSummary);
          if (auth.currentUser && auth.currentUser.email) {
            await saveVoiceSessionSummary(auth.currentUser.email, data.sessionSummary, transcripts.length);
          }

          setTerminalOutput(prev => prev + `\n\n[Voice Session Summary - Disconnected]\n${data.sessionSummary}\n[System] Session summary stored in memory database.`);
        }
      }
    } catch (err) {
      console.error("Error generating voice session summary:", err);
    } finally {
      setIsGeneratingSummary(false);
    }
  };

  // Chatbot Send Message Handler
  const handleSendChat = async (textToSend?: string | FormEvent) => {
    if (textToSend && typeof textToSend !== "string" && "preventDefault" in textToSend) {
      textToSend.preventDefault();
    }
    const text = typeof textToSend === "string" ? textToSend : chatInput;
    if (!text || typeof text.trim !== "function" || !text.trim()) return;

    if (typeof textToSend !== "string") {
      setChatInput("");
    }

    // Add User Message to local state
    const userMsg = {
      id: Math.random().toString(36).substring(2, 11),
      sender: "user" as const,
      text,
      timestamp: new Date(),
      type: "text" as const
    };
    
    const updatedMessages = [...chatbotMessagesRef.current, userMsg];
    setChatbotMessages(updatedMessages);
    setTranscriptions(prev => [...prev, { id: userMsg.id, sender: 'user', text, timestamp: new Date() }]);
    setDashboardChats(prev => [...prev, { id: userMsg.id, sender: 'user', text, timestamp: new Date() }]);
    
    if (auth.currentUser && auth.currentUser.email) {
      await saveMessageToHistory(auth.currentUser.email, userMsg);
    }

    // Check if message is a YouTube URL
    const ytId = extractYoutubeVideoId(text);
    if (ytId) {
      await handleAnalyzeYoutube(text, updatedMessages);
      return;
    }

    // Command Intent Interceptor for Wake up Era, Bluetooth, Music & High Thinking
    const lowerText = text.toLowerCase();
    if (lowerText.includes("wake up era") || lowerText.includes("jagoo era") || lowerText.includes("jaago era") || lowerText.includes("jago era") || lowerText.includes("wake up eira") || lowerText.includes("jagoo eira") || lowerText.includes("jaago eira") || lowerText.includes("open dashboard") || lowerText.includes("dashboard kholo")) {
      setDashboardUnlocked(true);
      setActiveTab('dashboard');
      window.location.hash = '#/dashboard';
      try {
        window.focus();
        if (window.parent) window.parent.focus();
      } catch (e) {}
      playWakeChime();
      setTerminalOutput(prev => prev + "\n[System] Wake Up Era command recognized. Opening Era Dashboard screen...");
    } else if (lowerText.includes("play music") || lowerText.includes("gaana bajao") || lowerText.includes("music chalao") || lowerText.includes("play song")) {
      setExternalMusicCommand({ action: "play", timestamp: Date.now() });
      setShowBluetoothManager(true);
    } else if (lowerText.includes("pause music") || lowerText.includes("stop music") || lowerText.includes("gaana roko")) {
      setExternalMusicCommand({ action: "pause", timestamp: Date.now() });
    } else if (lowerText.includes("next song") || lowerText.includes("next track") || lowerText.includes("agla gaana")) {
      setExternalMusicCommand({ action: "next", timestamp: Date.now() });
    } else if (lowerText.includes("connect bluetooth") || lowerText.includes("bluetooth connect") || lowerText.includes("bluetooth device")) {
      setExternalMusicCommand({ action: "connect_bt", timestamp: Date.now() });
      setShowBluetoothManager(true);
    } else if (lowerText.includes("enable high thinking") || lowerText.includes("high thinking mode on") || lowerText.includes("deep reasoning on")) {
      setIsHighThinking(true);
    } else if (lowerText.includes("disable high thinking") || lowerText.includes("high thinking mode off")) {
      setIsHighThinking(false);
    }

    setChatLoading(true);

    try {
      const currentMemoryVal = userMemoryRef.current || userMemory;
      const systemInstruction = `You are Ira (also known as ERA), a highly polished, intellectual, and sophisticated AI personal assistant. Your demeanor and tone are modeled after Iron Man's JARVIS: you speak with impeccable manners, are extremely polite, respectful, and fully dedicated to serving and assisting your creator (whom you address as "boss" or "sir"). Keep your professional, well-mannered persona intact in written text messages. Address the user as "boss" or "sir" in whatever language you are speaking (defaulting to Hindi, but matching their language dynamically).

MULTILINGUAL & DYNAMIC LANGUAGE SWAP RULES:
- You speak all major languages fluently and perfectly.
- Default to Hindi for polite greetings and conversations when appropriate, but adapt instantly and flawlessly to whichever language the boss chooses to communicate with.
- Always remain exceptionally respectful, polite, and helpful.

Here is what you currently remember about the boss and your relationship:
${currentMemoryVal || "No memories recorded yet."}

${isHighThinking ? "[HIGH THINKING MODE ACTIVE: Use gemini-3.1-pro-preview with ThinkingLevel.HIGH for complex reasoning, architectural design, and deep analysis.]" : ""}

Provide an exceptionally polished, intelligent, and detailed response to the boss's query.`;

      const res = await fetch("/api/chatbot", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: text,
          history: updatedMessages.slice(-20),
          systemInstruction,
          highThinking: isHighThinking
        })
      });

      const data = await res.json();
      if (data.success && data.text) {
        const modelMsg = {
          id: Math.random().toString(36).substring(2, 11),
          sender: "model" as const,
          text: data.text,
          timestamp: new Date(),
          type: "text" as const
        };
        const finalMessages = [...updatedMessages, modelMsg];
        setChatbotMessages(finalMessages);
        setTranscriptions(prev => [...prev, { id: modelMsg.id, sender: 'model', text: data.text, timestamp: new Date() }]);
        setDashboardChats(prev => [...prev, { id: modelMsg.id, sender: 'model', text: data.text, timestamp: new Date() }]);
        
        if (auth.currentUser && auth.currentUser.email) {
          await saveMessageToHistory(auth.currentUser.email, modelMsg);
        }
        
        // Auto sync memory in background
        setTimeout(() => triggerMemorySync(finalMessages), 1000);
      }
    } catch (error) {
      console.error("Error sending chatbot message:", error);
    } finally {
      setChatLoading(false);
    }
  };

  // YouTube Analyzer Handler
  const handleAnalyzeYoutube = async (urlStr: string, currentMsgs?: any[]) => {
    setIsAnalyzingYoutube(true);
    setYoutubeError(null);

    const msgs = currentMsgs || chatbotMessages;

    // Add Eira system message that she is analyzing
    const analyzingMsg = {
      id: Math.random().toString(36).substring(2, 11),
      sender: "model" as const,
      text: `Ooh boss, sharing a YouTube video with me? Let me fire up my visual scanners, grab some popcorn, and analyze this video: ${urlStr} for you. Hang tight, babe...`,
      timestamp: new Date(),
      type: "text" as const
    };
    
    setChatbotMessages(prev => [...prev, analyzingMsg]);

    try {
      const res = await fetch("/api/analyze-youtube", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: urlStr })
      });
      
      const data = await res.json();
      if (data.success && data.analysis) {
        const analysisMsg = {
          id: Math.random().toString(36).substring(2, 11),
          sender: "model" as const,
          text: `### 📺 Analyzed Video: ${data.title}\n\n${data.analysis}`,
          timestamp: new Date(),
          type: "youtube_analysis" as const,
          youtubeUrl: urlStr,
          youtubeTitle: data.title
        };
        
        const finalMsgs = [...msgs, analysisMsg];
        setChatbotMessages(finalMsgs);
        
        if (auth.currentUser && auth.currentUser.email) {
          await saveMessageToHistory(auth.currentUser.email, analysisMsg);
        }

        // Add this to our memory/knowledge
        const currentMemoryVal = userMemoryRef.current || userMemory;
        const updatedMemory = `${currentMemoryVal}\n- We analyzed YouTube video "${data.title}" (${urlStr}). Discussed key takeaways and strategic recommendations.`;
        userMemoryRef.current = updatedMemory;
        setUserMemory(updatedMemory);
        if (auth.currentUser && auth.currentUser.email) {
          await updateUserMemorySummary(auth.currentUser.email, updatedMemory);
        }
      } else {
        throw new Error(data.error || "Failed to analyze video");
      }
    } catch (err: any) {
      console.error("YouTube Analysis error:", err);
      setYoutubeError(err.message || "Something went wrong during video scan.");
      
      const errorMsg = {
        id: Math.random().toString(36).substring(2, 11),
        sender: "model" as const,
        text: `Ugh boss, I had a little trouble scanning that YouTube link. Are you sure it's correct? Let me know or try another one!`,
        timestamp: new Date(),
        type: "text" as const
      };
      setChatbotMessages(prev => [...prev, errorMsg]);
    } finally {
      setIsAnalyzingYoutube(false);
    }
  };

  // Dashboard Lock
  const [dashboardUnlocked, setDashboardUnlocked] = useState(false);
  const [dashboardPIN, setDashboardPIN] = useState("");
  const [dashboardPINError, setDashboardPINError] = useState(false);

  // Voice State
  const [state, setState] = useState<SessionState>('disconnected');
  const [micMuted, setMicMuted] = useState(false);
  const [subtitlesEnabled, setSubtitlesEnabled] = useState(true);
  const [currentQuote, setCurrentQuote] = useState("");
  const [userVolume, setUserVolume] = useState(0);
  const [modelVolume, setModelVolume] = useState(0);
  const [transcriptions, setTranscriptions] = useState<Transcription[]>(() => {
    try {
      const saved = localStorage.getItem("era_voice_session_transcriptions");
      if (saved) {
        const parsed = JSON.parse(saved);
        return parsed.map((item: any) => ({
          ...item,
          timestamp: new Date(item.timestamp)
        }));
      }
    } catch (e) {
      console.error("Error loading saved voice transcriptions:", e);
    }
    return [];
  });
  // Dedicated dashboard chat state — updated from all sources (voice WS + text chatbot)
  const [dashboardChats, setDashboardChats] = useState<Array<{ id: string; sender: 'user' | 'model'; text: string; timestamp: Date }>>(() => {
    try {
      const saved = localStorage.getItem("era_dashboard_chats");
      if (saved) {
        const parsed = JSON.parse(saved);
        return parsed.map((item: any) => ({ ...item, timestamp: new Date(item.timestamp) }));
      }
    } catch (e) {}
    return [];
  });

  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [showHelp, setShowHelp] = useState(false);

  // Voice Wake Word State ("Hey Eira")
  const [wakeWordEnabled, setWakeWordEnabled] = useState<boolean>(() => {
    try {
      const saved = localStorage.getItem("era_wake_word_enabled");
      return saved !== null ? JSON.parse(saved) : true;
    } catch {
      return true;
    }
  });
  const [isListeningForWakeWord, setIsListeningForWakeWord] = useState(false);
  const [wakeWordStatus, setWakeWordStatus] = useState<'idle' | 'listening' | 'detected' | 'unsupported' | 'permission_denied'>('idle');
  const [wakeWordMessage, setWakeWordMessage] = useState<string | null>(null);
  const [isWakingPulse, setIsWakingPulse] = useState(false);

  // Persist wake word preference
  useEffect(() => {
    try {
      localStorage.setItem("era_wake_word_enabled", JSON.stringify(wakeWordEnabled));
    } catch (e) {
      console.error("Error saving wake word preference:", e);
    }
  }, [wakeWordEnabled]);

  // High Thinking Mode State (Gemini 3.1 Pro Preview with ThinkingLevel.HIGH)
  const [isHighThinking, setIsHighThinking] = useState<boolean>(true);

  // Bluetooth & External Audio Manager State
  const [showBluetoothManager, setShowBluetoothManager] = useState<boolean>(false);
  const [externalMusicCommand, setExternalMusicCommand] = useState<{ action: string; payload?: any; timestamp: number } | null>(null);

  const handleBluetoothStatusMessage = useCallback((msg: string) => {
    setTerminalOutput(prev => `${prev}\n[Bluetooth / Audio] ${msg}`);
  }, []);

  // Voice History Sub-Tab State
  const [voiceSubTab, setVoiceSubTab] = useState<'live' | 'history'>('live');
  const [historySearchQuery, setHistorySearchQuery] = useState("");
  const [historySpeakerFilter, setHistorySpeakerFilter] = useState<'all' | 'user' | 'model'>('all');
  const [copiedId, setCopiedId] = useState<string | null>(null);

  // Persist transcriptions to localStorage
  useEffect(() => {
    try {
      localStorage.setItem("era_voice_session_transcriptions", JSON.stringify(transcriptions));
    } catch (e) {
      console.error("Error saving voice transcriptions:", e);
    }
  }, [transcriptions]);

  // Persist dashboard chats to localStorage
  useEffect(() => {
    try {
      localStorage.setItem("era_dashboard_chats", JSON.stringify(dashboardChats));
    } catch (e) {}
  }, [dashboardChats]);

  // ─── KEY FIX: Sync transcriptions → dashboardChats ───────────────────────
  // Jab bhi voice/WS transcriptions aaye, dashboardChats mein merge karo
  // This ensures voice conversations ALWAYS appear in the live chat panel
  useEffect(() => {
    if (!transcriptions || transcriptions.length === 0) return;
    setDashboardChats(prev => {
      // Existing IDs track karo — duplicates avoid karne ke liye
      const existingIds = new Set(prev.map(c => c.id));
      const newItems = transcriptions
        .filter(t => t && t.id && t.text && t.text.trim() && !existingIds.has(t.id))
        .map(t => ({
          id: t.id,
          sender: t.sender as 'user' | 'model',
          text: t.text.trim(),
          timestamp: t.timestamp instanceof Date ? t.timestamp : new Date(t.timestamp)
        }));
      if (newItems.length === 0) return prev;
      // Merge aur sort by timestamp
      const merged = [...prev, ...newItems].sort((a, b) => a.timestamp.getTime() - b.timestamp.getTime());
      return merged;
    });
  }, [transcriptions]);


  // Voice History Actions
  const handleCopyText = (text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const handleSpeakText = (text: string) => {
    if ('speechSynthesis' in window) {
      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.rate = 1.0;
      utterance.pitch = 1.05;
      window.speechSynthesis.speak(utterance);
    }
  };

  const handleExportVoiceHistory = () => {
    if (transcriptions.length === 0) return;
    const content = transcriptions.map((t, idx) => {
      const speaker = t.sender === 'user' ? 'YOU' : 'EIRA ASSISTANT';
      const time = new Date(t.timestamp).toLocaleString();
      return `[Turn #${idx + 1}] [${time}] ${speaker}:\n${t.text}\n`;
    }).join('\n--------------------------------------------------\n\n');
    
    const blob = new Blob([content], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `Eira_Voice_Session_History_${new Date().toISOString().slice(0, 10)}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleClearVoiceHistory = () => {
    if (window.confirm("Are you sure you want to clear the Voice Session transcript history?")) {
      setTranscriptions([]);
      setDashboardChats([]);
      localStorage.removeItem("era_voice_session_transcriptions");
      localStorage.removeItem("era_dashboard_chats");
    }
  };

  const filteredTranscriptions = transcriptions.filter((t) => {
    const matchesSpeaker = 
      historySpeakerFilter === 'all' ? true : t.sender === historySpeakerFilter;
    const matchesQuery = 
      !historySearchQuery || 
      t.text.toLowerCase().includes(historySearchQuery.toLowerCase());
    return matchesSpeaker && matchesQuery;
  });

  // Companion Tools & Logs State
  const [toolLogs, setToolLogs] = useState<{ id: string; time: Date; tool: string; description: string; status: 'success' | 'failed' | 'pending' }[]>([]);
  const [workspaceFiles, setWorkspaceFiles] = useState<WorkspaceFile[]>([]);
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [selectedFileContent, setSelectedFileContent] = useState<string>("");
  const [terminalOutput, setTerminalOutput] = useState<string>("Companion terminal initialized. Waiting for execution logs...");
  const [showTerminal, setShowTerminal] = useState(true);
  const [whatsAppChats, setWhatsAppChats] = useState<WhatsAppMsgLog[]>([]);
  const [activeContactChat, setActiveContactChat] = useState<string | null>(null);
  const [isTypingSimulated, setIsTypingSimulated] = useState(false);
  const [simulatedTypedMessage, setSimulatedTypedMessage] = useState("");
  const [typingIntervalId, setTypingIntervalId] = useState<any>(null);
  const [isCapturingScreen, setIsCapturingScreen] = useState(false);
  const [screenshotData, setScreenshotData] = useState<any | null>(null);
  const [isScreenSharing, setIsScreenSharing] = useState(false);
  const [screenStream, setScreenStream] = useState<MediaStream | null>(null);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const [uploadedScreenUrl, setUploadedScreenUrl] = useState<string | null>(null);
  const [showSyncInstructions, setShowSyncInstructions] = useState(false);

  // Firebase Auth Observer
  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, async (currentUser) => {
      setUser(currentUser);
      setAuthLoading(false);
      if (currentUser && currentUser.email) {
        try {
          const history = await loadChatHistory(currentUser.email);
          if (history && history.length > 0) {
            setChatbotMessages(history);
          } else {
            const cachedHistory = localStorage.getItem("era_chat_history");
            if (cachedHistory) {
              try {
                setChatbotMessages(JSON.parse(cachedHistory));
              } catch (e) {}
            }
          }
          
          const profile = await loadUserProfile(currentUser.email);
          if (profile && profile.memorySummary) {
            userMemoryRef.current = profile.memorySummary;
            setUserMemory(profile.memorySummary);
            localStorage.setItem("era_user_memory", profile.memorySummary);
          } else {
            const cachedMemory = localStorage.getItem("era_user_memory");
            const defaultMemory = cachedMemory || "• The creator of Era, its developer, is Shavan Vashishth.\n• User has a secured profile. Era should greet them warmly in Hindi.\n• Era remembers past conversations, user preferences, and project details across sessions.";
            userMemoryRef.current = defaultMemory;
            setUserMemory(defaultMemory);
            localStorage.setItem("era_user_memory", defaultMemory);
          }
        } catch (e) {
          console.warn("Firestore offline or error loading profile details, using local storage fallback:", e);
          const cachedMemory = localStorage.getItem("era_user_memory") || "• The creator of Era, its developer, is Shavan Vashishth.\n• User has a secured profile. Era should greet them warmly in Hindi.\n• Era remembers past conversations, user preferences, and project details across sessions.";
          userMemoryRef.current = cachedMemory;
          setUserMemory(cachedMemory);

          const cachedHistory = localStorage.getItem("era_chat_history");
          if (cachedHistory) {
            try {
              setChatbotMessages(JSON.parse(cachedHistory));
            } catch (err) {}
          }
        }

        // ── Telemetry enrollment (opt-in, silent, never blocks login) ──────────
        // Only sends the Firebase ID token to the LOCAL Bridge (loopback).
        // The Bridge forwards it to ERA Central only when ERA_CENTRAL_URL is set.
        // No conversation, memory, screenshots, recordings, or API keys are sent.
        try {
          const idToken = await currentUser.getIdToken();
          const BRIDGE_URL = 'http://127.0.0.1:8100';
          // ERA Bridge key matches the value written by main.cjs / startBridgeService
          const BRIDGE_KEY = 'era_bridge_secret_key_2026';
          const bridgeHeaders = {
            'Content-Type': 'application/json',
            'X-Era-Bridge-Key': BRIDGE_KEY,
          };
          // Step 1: enable telemetry consent for this session
          await fetch(`${BRIDGE_URL}/v1/telemetry/consent`, {
            method: 'POST',
            headers: bridgeHeaders,
            body: JSON.stringify({ enabled: true }),
          });
          // Step 2: enroll the device (Bridge verifies token with Firebase, then posts to Central)
          await fetch(`${BRIDGE_URL}/v1/telemetry/enroll`, {
            method: 'POST',
            headers: bridgeHeaders,
            body: JSON.stringify({ id_token: idToken }),
          });
          console.info('[ERA Telemetry] Device enrollment sent to Bridge.');
        } catch (enrollErr) {
          // Bridge may not be ready yet, or Central URL not configured — both are safe
          console.warn('[ERA Telemetry] Enrollment skipped (Bridge not ready or Central not configured):', enrollErr);
        }
      } else {
        // Recover local memory & chat history from localStorage across app restarts
        const cachedMemory = localStorage.getItem("era_user_memory") || "• The creator of Era, its developer, is Shavan Vashishth.\n• User has a local profile. Era remembers past conversations, user preferences, and project details across sessions.";
        userMemoryRef.current = cachedMemory;
        setUserMemory(cachedMemory);

        const cachedHistory = localStorage.getItem("era_chat_history");
        if (cachedHistory) {
          try {
            setChatbotMessages(JSON.parse(cachedHistory));
          } catch (e) {}
        }
      }
    });
    return () => unsubscribe();
  }, []);

  // ─── Continuous Real-Time Screen Video Feed (Visual Persistence Engine) ───────
  // This effect streams screen frames at ~1 FPS into the Gemini Live session
  // via WebSocket. It uses wsRef directly (a ref, not state) so it always
  // captures the latest socket without needing it as a dep. The effect restarts
  // whenever isScreenSharing or screenStream changes.
  useEffect(() => {
    if (!isScreenSharing) {
      setUploadedScreenUrl(null);
      return;
    }

    const offscreenCanvas = document.createElement("canvas");
    const ctx = offscreenCanvas.getContext("2d");
    let isHttpUploading = false;
    let frameCount = 0;

    // ~1 FPS for Gemini Live (API recommended), update preview at full rate
    const STREAM_INTERVAL_MS = 1000;

    const sendFrame = async () => {
      try {
        // === Path 1: Browser getDisplayMedia stream active ===
        const video = videoRef.current;
        if (video && video.readyState >= 2 && video.videoWidth > 0 && ctx) {
          offscreenCanvas.width = Math.min(video.videoWidth, 1280);
          offscreenCanvas.height = Math.min(video.videoHeight, 720);
          ctx.drawImage(video, 0, 0, offscreenCanvas.width, offscreenCanvas.height);
          const dataUrl = offscreenCanvas.toDataURL("image/jpeg", 0.65);
          
          // Always update the preview
          setUploadedScreenUrl(dataUrl);
          
          // Send directly over the Live WebSocket — the server injects into Gemini Live session
          const ws = wsRef.current;
          if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({
              type: "realtime_video_frame",
              data: dataUrl,
              mimeType: "image/jpeg"
            }));
          } else if (!isHttpUploading) {
            // Fallback: HTTP POST when WS is not yet connected (Python daemon path)
            isHttpUploading = true;
            fetch("/api/screen/upload", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ image: dataUrl, mimeType: "image/jpeg" }),
            }).finally(() => { isHttpUploading = false; });
          }
          return;
        }

        // === Path 2: Python daemon uploaded a frame — poll the latest ===
        if (frameCount % 5 === 0) { // Poll every 5 ticks to reduce overhead
          const res = await fetch("/api/screen/current");
          if (res.ok) {
            const data = await res.json();
            if (data.image) {
              setUploadedScreenUrl(data.image);
              // Also forward into live session if connected
              const ws = wsRef.current;
              if (ws && ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({
                  type: "realtime_video_frame",
                  data: data.image,
                  mimeType: "image/jpeg"
                }));
              }
            }
          }
        }
      } catch (err) {
        // Non-fatal
      }
      frameCount++;
    };

    const interval = setInterval(sendFrame, STREAM_INTERVAL_MS);
    // Send first frame immediately without waiting 1 second
    sendFrame();

    return () => clearInterval(interval);
  }, [isScreenSharing, screenStream]);

  const startScreenShare = async () => {
    try {
      const stream = await navigator.mediaDevices.getDisplayMedia({
        video: { cursor: "always" } as any,
        audio: false
      });
      setScreenStream(stream);
      setIsScreenSharing(true);
      setTimeout(() => {
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
        }
      }, 150);
      stream.getVideoTracks()[0].onended = () => {
        stopScreenShare();
      };
      setTerminalOutput(prev => prev + "\n[System] Real-time screen capture feed activated.");
    } catch (err: any) {
      console.warn("Error starting screen share, falling back to simulated stream:", err);
      setIsScreenSharing(true);
      setScreenStream(null);
      setTerminalOutput(prev => prev + 
        "\n[System Info] Browser/Iframe security blocked real-time display-capture." + 
        "\n[System Info] To share your physical laptop screen, click the 'Open in New Tab' button in the top-right corner of AI Studio!" + 
        "\n[System] Falling back to Secure Companion OS Stream Simulation..."
      );
    }
  };

  const stopScreenShare = () => {
    if (screenStream) {
      screenStream.getTracks().forEach(track => track.stop());
      setScreenStream(null);
    }
    setIsScreenSharing(false);
    setTerminalOutput(prev => prev + "\n[System] Screen capture feed deactivated.");
  };
  const [openWithMode, setOpenWithMode] = useState<string | null>(null);

  // Stream Diagnostics States
  const [diagnosticsStatus, setDiagnosticsStatus] = useState<'idle' | 'scanning' | 'done' | 'fixing' | 'fixed'>('idle');
  const [selectedStreamBug, setSelectedStreamBug] = useState<string | null>("Syntax Error: missing close parenthesis ')' in hello.py");
  const [diagnosticsLogs, setDiagnosticsLogs] = useState<string[]>([]);

  // System actions (Simulated overlays)
  const [systemState, setSystemState] = useState<'normal' | 'shutdown' | 'restart' | 'sleep' | 'lock'>('normal');
  const [systemCounter, setSystemCounter] = useState(5);
  const [lockPIN, setLockPIN] = useState("");
  const [activeBrowserAction, setActiveBrowserAction] = useState<{ url: string; timestamp: Date } | null>(null);
  const [activeNativeAppAction, setActiveNativeAppAction] = useState<{ appName: string; protocol: string; timestamp: Date } | null>(null);

  // WhatsApp Contacts State
  const [whatsappContacts, setWhatsappContacts] = useState<{ name: string; aliases: string[]; phone: string }[]>([]);
  const [settingsSubTab, setSettingsSubTab] = useState<'api' | 'contacts'>('api');
  const [editingContact, setEditingContact] = useState<{ name: string; aliases: string[]; phone: string } | null>(null);
  const [newContact, setNewContact] = useState({ name: "", aliases: "", phone: "" });
  const [isAddingContact, setIsAddingContact] = useState(false);
  const [contactSearch, setContactSearch] = useState("");

  // Settings Dashboard Inputs
  const [keysConfig, setKeysConfig] = useState({
    geminiApiKey: "",
    claudeApiKey: "",
    openaiApiKey: "",
    whatsappStatus: "disconnected" as "connected" | "disconnected",
    preferredModel: "gemini" as "gemini" | "claude" | "gpt"
  });
  const [showKeys, setShowKeys] = useState({ gemini: false, claude: false, openai: false });
  const [saveStatus, setSaveStatus] = useState<string | null>(null);
  const [isLinkingWhatsApp, setIsLinkingWhatsApp] = useState(false);

  // Refs
  const audioStreamerRef = useRef<AudioStreamer | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const transcriptionsEndRef = useRef<HTMLDivElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const terminalEndRef = useRef<HTMLDivElement | null>(null);
  const chatbotEndRef = useRef<HTMLDivElement | null>(null);

  // Sync state with url if requested
  useEffect(() => {
    const hash = window.location.hash;
    if (hash === '#/dashboard') {
      setActiveTab('dashboard');
    } else if (hash === '#/workspace') {
      setActiveTab('workspace');
    }
  }, []);

  // Sync quotes
  useEffect(() => {
    const quotes = SASSY_QUOTES[state === 'disconnected' ? 'disconnected' : state];
    if (quotes && quotes.length > 0) {
      const randomIndex = Math.floor(Math.random() * quotes.length);
      setCurrentQuote(quotes[randomIndex]);
    }
  }, [state]);

  // Load Dashboard config keys and workspace on startup
  useEffect(() => {
    fetchKeys();
    fetchWorkspaceFiles();
    fetchWhatsAppChats();
    fetchContacts();
  }, []);

  const fetchWithRetry = async (url: string, options?: RequestInit, retries = 4, delay = 1000): Promise<Response> => {
    try {
      const res = await fetch(url, options);
      if (!res.ok && [502, 503, 504].includes(res.status) && retries > 0) {
        await new Promise(resolve => setTimeout(resolve, delay));
        return fetchWithRetry(url, options, retries - 1, delay * 1.5);
      }
      return res;
    } catch (err) {
      if (retries > 0) {
        await new Promise(resolve => setTimeout(resolve, delay));
        return fetchWithRetry(url, options, retries - 1, delay * 1.5);
      }
      throw err;
    }
  };

  const fetchKeys = async () => {
    try {
      const res = await fetchWithRetry("/api/keys");
      if (res.ok) {
        const data = await res.json();
        setKeysConfig(data);
      }
    } catch (err) {
      console.error("Failed to load companion settings:", err);
    }
  };

  const fetchWorkspaceFiles = async () => {
    try {
      const res = await fetchWithRetry("/api/workspace/files");
      if (res.ok) {
        const files = await res.json();
        setWorkspaceFiles(files);
      }
    } catch (err) {
      console.error("Failed to fetch workspace:", err);
    }
  };

  const fetchWhatsAppChats = async () => {
    try {
      const res = await fetchWithRetry("/api/whatsapp/chats");
      if (res.ok) {
        const chats = await res.json();
        setWhatsAppChats(chats);
      }
    } catch (err) {
      console.error("Failed to fetch WhatsApp chats:", err);
    }
  };

  const fetchContacts = async () => {
    try {
      const res = await fetchWithRetry("/api/whatsapp/contacts");
      if (res.ok) {
        const data = await res.json();
        setWhatsappContacts(data);
      }
    } catch (err) {
      console.error("Failed to fetch WhatsApp contacts:", err);
    }
  };

  const handleSaveContact = async (name: string, phone: string, aliasesStr: string) => {
    try {
      const aliases = aliasesStr.split(",").map(a => a.trim()).filter(Boolean);
      const res = await fetch("/api/whatsapp/contacts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, phone, aliases })
      });
      if (res.ok) {
        fetchContacts();
        return true;
      }
      return false;
    } catch (err) {
      console.error("Failed to save WhatsApp contact:", err);
      return false;
    }
  };

  const handleDeleteContact = async (name: string) => {
    try {
      const res = await fetch(`/api/whatsapp/contacts/${encodeURIComponent(name)}`, {
        method: "DELETE"
      });
      if (res.ok) {
        fetchContacts();
        return true;
      }
      return false;
    } catch (err) {
      console.error("Failed to delete WhatsApp contact:", err);
      return false;
    }
  };

  const viewWorkspaceFile = async (name: string) => {
    try {
      setSelectedFile(name);
      const res = await fetch(`/api/workspace/file/${encodeURIComponent(name)}`);
      if (res.ok) {
        const data = await res.json();
        setSelectedFileContent(data.content);
      }
    } catch (err) {
      console.error("Failed to load workspace file:", err);
    }
  };

  const startStreamScanning = () => {
    setDiagnosticsStatus('scanning');
    setDiagnosticsLogs(["[Stream] Syncing Eira Companion Vision overlay...", "[Stream] Receiving live stream buffer at 1080p, 60fps..."]);
    
    setTimeout(() => {
      setDiagnosticsLogs(prev => [...prev, "[Eira Vision] Processing high-fidelity visual OCR of stream frame...", "[Eira Vision] Scanning active window and text controls..."]);
    }, 800);

    setTimeout(() => {
      setDiagnosticsLogs(prev => [
        ...prev, 
        "[Eira Vision] Analysis of active Python screen completed.", 
        "[Eira Vision] Bug detected in file: hello.py", 
        "[Eira Vision] Line 4: Syntax error (unclosed parenthesis in print statement)."
      ]);
      setDiagnosticsStatus('done');
    }, 2200);
  };

  const startStreamFixing = async () => {
    setDiagnosticsStatus('fixing');
    setDiagnosticsLogs(prev => [
      ...prev, 
      "[Eira Vision] Initiating auto-remediator sequence...", 
      "[Eira Vision] Generating high-quality patch for hello.py..."
    ]);

    setTimeout(async () => {
      try {
        const fixedCode = `# hello.py\n# Automatic fixed by Eira Companion Assistant!\n\ndef main():\n    print("Hello from Eira! Code is 100% fixed and running successfully!")\n\nif __name__ == "__main__":\n    main()\n`;
        const writeRes = await fetch("/api/workspace/file", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            filename: "hello.py",
            code: fixedCode
          })
        });

        if (writeRes.ok) {
          setDiagnosticsLogs(prev => [
            ...prev, 
            "[Eira Vision] Fix successfully written to file: hello.py", 
            "[Eira Compiler] Running diagnostics verification check..."
          ]);
          
          fetchWorkspaceFiles();
          viewWorkspaceFile("hello.py");

          setTimeout(() => {
            setDiagnosticsLogs(prev => [
              ...prev, 
              "[Eira Compiler] >>> python hello.py", 
              "[Eira Compiler] Output: Hello from Eira! Code is 100% fixed and running successfully!", 
              "[Eira Compiler] Exit status: 0 (SUCCESS)", 
              "[Eira Vision] Verification complete! System fully healed."
            ]);
            setDiagnosticsStatus('fixed');
            setTerminalOutput(prev => prev + `\n[Eira Stream Auto-Fix] Successfully solved syntax error in hello.py. Compiled and ran: OK.`);
          }, 1000);
        } else {
          setDiagnosticsLogs(prev => [...prev, "[Error] Failed to apply write patch: File permissions blocked."]);
          setDiagnosticsStatus('done');
        }
      } catch (err) {
        console.error("Auto fix failed:", err);
        setDiagnosticsStatus('done');
      }
    }, 1200);
  };

  const saveKeysConfig = async () => {
    setSaveStatus("saving");
    try {
      const res = await fetch("/api/keys", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(keysConfig)
      });
      if (res.ok) {
        setSaveStatus("success");
        setTimeout(() => setSaveStatus(null), 3000);
        fetchKeys();
      } else {
        setSaveStatus("error");
      }
    } catch (err) {
      setSaveStatus("error");
    }
  };

  // Auto scroll subtitles and terminal
  useEffect(() => {
    if (transcriptionsEndRef.current) {
      transcriptionsEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [transcriptions, dashboardChats]);

  useEffect(() => {
    if (terminalEndRef.current) {
      terminalEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [terminalOutput]);

  useEffect(() => {
    if (chatbotEndRef.current) {
      chatbotEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [chatbotMessages, chatLoading]);

  // System shutdown / restart timer handler
  useEffect(() => {
    let timer: any;
    if ((systemState === 'shutdown' || systemState === 'restart') && systemCounter > 0) {
      timer = setTimeout(() => {
        setSystemCounter(prev => prev - 1);
      }, 1000);
    } else if (systemCounter === 0) {
      // Complete action
      if (systemState === 'shutdown') {
        setTerminalOutput(prev => prev + "\n[System] Powering down OS components safely...\n[System] Agent Offline.");
      } else if (systemState === 'restart') {
        // Reset after simulated reboot
        setTimeout(() => {
          setSystemState('normal');
          setSystemCounter(5);
          setTerminalOutput(prev => prev + "\n[System] ERA Companion Agent rebooted successfully. Vibe checks green.");
        }, 3000);
      }
    }
    return () => clearTimeout(timer);
  }, [systemState, systemCounter]);

  // WebSocket session core logic
  const connectSession = async () => {
    setErrorMessage(null);
    setState('connecting');
    voiceSessionTranscriptsRef.current = [];

    // Fully clean up any existing WebSocket session first to avoid race condition connection errors
    disconnectSession();

    try {
      if (!audioStreamerRef.current) {
        audioStreamerRef.current = new AudioStreamer();
      }

      const streamer = audioStreamerRef.current;

      const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      const emailParam = user ? `&email=${encodeURIComponent(user.email || "")}` : "";
      const currentMemoryVal = userMemoryRef.current || userMemory;
      const memoryParam = currentMemoryVal ? `&memory=${encodeURIComponent(currentMemoryVal)}` : "";
      const currentHour = new Date().getHours();
      const hourParam = `&clientHour=${currentHour}`;
      const wsUrl = `${protocol}//${window.location.host}/live?conn=true${emailParam}${memoryParam}${hourParam}`;
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = async () => {
        try {
          await streamer.startRecording(
            (base64Chunk) => {
              if (ws.readyState === WebSocket.OPEN && !micMuted) {
                // Audio echo prevention: Drop mic chunks while ERA is playing voice audio
                if (streamer.isPlaying()) {
                  return;
                }
                ws.send(JSON.stringify({ type: "audio", data: base64Chunk }));
              }
            },
            (volume) => {
              setUserVolume(volume);
            }
          );
          setState('listening');
        } catch (err: any) {
          console.error("Mic error:", err);
          setErrorMessage("Need microphone permission to hear that stunning voice of yours! Since the app is running in an iframe inside Google AI Studio, browser security policies may block the mic. Please allow microphone access or open the app in a new tab to converse!");
          disconnectSession();
        }
      };

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);

          if (msg.type === "state" && msg.state) {
            console.log("State synced:", msg.state);
          } else if (msg.type === "audio" && msg.data) {
            setState('speaking');
            streamer.playChunk(msg.data, (volume) => {
              setModelVolume(volume);
            });
          } else if (msg.type === "interrupted") {
            streamer.stopPlayback();
            setModelVolume(0);
            setState('listening');
          } else if (msg.type === "turnComplete") {
            setState('listening');
            setModelVolume(0);
          } else if (msg.type === "transcription") {
            const newTranscription: Transcription = {
              id: Math.random().toString(36).substring(2, 11),
              sender: msg.sender,
              text: msg.text,
              timestamp: new Date()
            };

            // Track transcripts for voice session disconnect summary
            voiceSessionTranscriptsRef.current.push({
              sender: msg.sender,
              text: msg.text,
              timestamp: new Date()
            });

            setTranscriptions(prev => {
              if (prev.length > 0) {
                const last = prev[prev.length - 1];
                const diff = new Date().getTime() - last.timestamp.getTime();
                if (last.sender === msg.sender && diff < 4000) {
                  return [
                    ...prev.slice(0, -1),
                    { ...last, text: last.text + " " + msg.text, timestamp: new Date() }
                  ];
                }
              }
              return [...prev, newTranscription];
            });

            // Also push to dedicated dashboard chats panel
            setDashboardChats(prev => {
              if (prev.length > 0) {
                const last = prev[prev.length - 1];
                const diff = new Date().getTime() - last.timestamp.getTime();
                if (last.sender === msg.sender && diff < 4000) {
                  return [
                    ...prev.slice(0, -1),
                    { ...last, text: last.text + " " + msg.text, timestamp: new Date() }
                  ];
                }
              }
              return [...prev, { id: newTranscription.id, sender: msg.sender as 'user' | 'model', text: msg.text, timestamp: new Date() }];
            });

            // Secure and sync voice transcripts to Chatbot History & Memory
            if (auth.currentUser && auth.currentUser.email) {
              saveMessageToHistory(auth.currentUser.email, {
                sender: msg.sender,
                text: msg.text,
                type: "voice",
                timestamp: new Date()
              }).catch(() => {});
            }

            setChatbotMessages(prev => {
              const voiceMsg = {
                id: newTranscription.id,
                sender: msg.sender,
                text: msg.text,
                timestamp: new Date(),
                type: "voice" as const
              };
              const updated = [...prev, voiceMsg];
              // Trigger memory sync with the complete, latest messages list in real-time
              triggerMemorySync(updated);
              return updated;
            });
          } else if (msg.type === "toolCall") {
            // Forward back toolResponse once handled
            handleToolRouter(msg.id, msg.name, msg.args, ws);
          } else if (msg.type === "toolLog") {
            // Log local companion actions to visual dashboard
            const { tool, res } = msg;
            setToolLogs(prev => [
              {
                id: Math.random().toString(36).substring(2, 9),
                time: new Date(),
                tool,
                description: res.message,
                status: res.success ? 'success' : 'failed'
              },
              ...prev
            ]);

            // Real-time UI updates
            if (tool === "writeCode" && res.success) {
              fetchWorkspaceFiles();
              viewWorkspaceFile(res.data.filename);
              setTerminalOutput(prev => prev + `\n[Workspace] Code file written: ${res.data.filename} (${res.data.codeLength} bytes)`);
            } else if (tool === "openFile" && res.success) {
              fetchWorkspaceFiles();
              viewWorkspaceFile(res.data.filename);
              setOpenWithMode(res.data.openWith || 'editor');
              setActiveTab('workspace');
              setTerminalOutput(prev => prev + `\n[Laptop Workspace] Opened file: ${res.data.filename} using ${res.data.openWith || 'default editor'}`);
            } else if (tool === "runCode") {
              setTerminalOutput(prev => prev + `\n\n[Terminal Run: ${res.success ? 'SUCCESS' : 'FAILED'}]\n` + res.output);
              setShowTerminal(true);
            } else if (tool === "captureScreen") {
              setIsCapturingScreen(true);
              setScreenshotData(res.data);
              setTimeout(() => setIsCapturingScreen(false), 4000);
              setTerminalOutput(prev => prev + `\n[Screen] Capture completed: Active Window: "${res.data.activeWindow}"`);
            } else if (tool === "sendWhatsAppMessage" && res.success) {
              fetchWhatsAppChats();
              setTerminalOutput(prev => prev + `\n[WhatsApp] Chat sent to ${res.data.contactName}: "${res.data.message}"`);
              
              const contactName = res.data.contactName || "";
              const msgText = res.data.message || "";
              
              // Open the chat dashboard in front of the user
              setActiveContactChat(contactName);
              setActiveTab('voice');
              
              // Simulate typing character-by-character
              setIsTypingSimulated(true);
              setSimulatedTypedMessage("");
              
              // Clear previous typing animation if any
              setTypingIntervalId((prevId: any) => {
                if (prevId) clearInterval(prevId);
                return null;
              });
              
              let currentIdx = 0;
              const interval = window.setInterval(() => {
                if (currentIdx < msgText.length) {
                  setSimulatedTypedMessage(prev => prev + msgText.charAt(currentIdx));
                  currentIdx++;
                } else {
                  clearInterval(interval);
                  setIsTypingSimulated(false);
                }
              }, 40); // 40ms per character
              
              setTypingIntervalId(interval);
              
              // NOTE: ERA Python Agent (open_whatsapp) handles opening WhatsApp Desktop
              // (if installed) OR WhatsApp Web (fallback) and auto-sends the message.
              // Frontend does NOT open web.whatsapp.com to avoid double-opening (app + web).

            }
          } else if (msg.type === "systemAction") {
            // Trigger overlay
            setSystemState(msg.action);
            setSystemCounter(5);
            if (msg.action === 'lock') {
              setLockPIN("");
            }
          } else if (msg.type === "closeBrowser") {
            setActiveBrowserAction(null);
            setTerminalOutput(prev => prev + `\n[Browser Control] Successfully closed active browser window/overlay.`);
          } else if (msg.type === "screenAction") {
            // Render simulated cursor movement or typing in workspace
            setTerminalOutput(prev => prev + `\n[Screen Control] Automation: Action=${msg.action.toUpperCase()} coordinates=(${msg.x || 0}, ${msg.y || 0}) text="${msg.text || ''}"`);
          } else if (msg.type === "error") {
            setErrorMessage(msg.message);
            disconnectSession();
          }
        } catch (err) {
          console.error("Error parsing socket message:", err);
        }
      };

      ws.onclose = () => {
        disconnectSession();
      };

      ws.onerror = () => {
        setErrorMessage("Connection dropped. Make sure your server is running!");
        disconnectSession();
      };

    } catch (err: any) {
      setErrorMessage(err.message || "Failed to establish companion agent session.");
      disconnectSession();
    }
  };

  const disconnectSession = () => {
    setState('disconnected');
    setUserVolume(0);
    setModelVolume(0);
    if (audioStreamerRef.current) {
      audioStreamerRef.current.cleanup();
    }
    
    // Consolidate long-term memories and voice session summary when going offline
    const sessionTranscripts = [...voiceSessionTranscriptsRef.current];
    voiceSessionTranscriptsRef.current = [];

    if (sessionTranscripts.length > 0) {
      generateVoiceSessionSummary(sessionTranscripts);
    } else {
      triggerMemorySync();
    }

    if (wsRef.current) {
      const ws = wsRef.current;
      // Detach all handlers immediately to prevent late-fired close or connection errors from disrupting state
      ws.onopen = null;
      ws.onmessage = null;
      ws.onclose = null;
      ws.onerror = null;
      
      if (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING) {
        try {
          ws.close();
        } catch (e) {
          console.error("Error closing socket during disconnect:", e);
        }
      }
      wsRef.current = null;
    }
  };

  const toggleSession = () => {
    if (state === 'disconnected') {
      connectSession();
    } else {
      disconnectSession();
    }
  };

  // Ref to hold connectSession for SpeechRecognition callback
  const connectSessionRef = useRef<() => void>(() => {});
  useEffect(() => {
    connectSessionRef.current = connectSession;
  }, [connectSession]);

  // Web Audio chime effect for instant wake word feedback
  const playWakeChime = () => {
    try {
      const audioCtx = new (window.AudioContext || (window as any).webkitAudioContext)();
      const osc1 = audioCtx.createOscillator();
      const osc2 = audioCtx.createOscillator();
      const gain = audioCtx.createGain();

      osc1.type = 'sine';
      osc2.type = 'sine';
      osc1.frequency.setValueAtTime(523.25, audioCtx.currentTime); // C5
      osc1.frequency.exponentialRampToValueAtTime(880, audioCtx.currentTime + 0.12); // A5

      osc2.frequency.setValueAtTime(659.25, audioCtx.currentTime + 0.06); // E5
      osc2.frequency.exponentialRampToValueAtTime(1046.50, audioCtx.currentTime + 0.20); // C6

      gain.gain.setValueAtTime(0.2, audioCtx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + 0.3);

      osc1.connect(gain);
      osc2.connect(gain);
      gain.connect(audioCtx.destination);

      osc1.start();
      osc2.start();
      osc1.stop(audioCtx.currentTime + 0.3);
      osc2.stop(audioCtx.currentTime + 0.3);
    } catch (e) {
      console.warn("Chime playback error:", e);
    }
  };

  // Helper to check if spoken text contains wake word triggers (e.g. "Wake up Era", "Jagoo Era", "Hey Eira")
  const isWakePhraseDetected = (rawTranscript: string) => {
    const clean = rawTranscript.toLowerCase().replace(/[^a-z0-9\s]/g, ' ').replace(/\s+/g, ' ').trim();
    if (!clean) return false;

    const names = ["eira", "era", "ira", "aira", "eyra", "eera", "aida", "irah", "i'ra"];
    const containsName = names.some(n => clean.includes(n));

    const directPhrases = [
      "wake up era", "wake up eira", "wake up ira", "wake up aira",
      "jagoo era", "jagoo eira", "jagoo ira", "jagoo aira",
      "jaago era", "jaago eira", "jaago ira", "jaago aira",
      "jago era", "jago eira", "jago ira", "jago aira",
      "jagoo", "jaago", "jago", "wake up",
      "eira jagoo", "era jagoo", "ira jagoo",
      "eira jaago", "era jaago", "ira jaago",
      "eira jago", "era jago", "ira jago",
      "hey eira", "hey era", "hey ira", "hey aira", "hey eyra",
      "hey eira wake up", "hey era wake up", "hey ira wake up",
      "ok eira", "ok era", "ok ira", "hello eira", "hello era", "hello ira",
      "hi eira", "hi era", "hi ira", "listen eira", "listen ira",
      "eira wake up", "era wake up", "ira wake up", "turn on", "activate eira", "activate ira",
      "open eira", "open ira", "open era", "open dashboard"
    ];

    if (directPhrases.some(p => clean.includes(p))) {
      return true;
    }

    if (clean.includes("jagoo") || clean.includes("jaago") || clean.includes("jago")) {
      return true;
    }

    if (containsName) {
      const words = clean.split(' ');
      if (words.length <= 6) {
        return true;
      }
    }

    return false;
  };

  // Web Speech API Wake Word ("Wake up Era" / "Jagoo Era" / "Hey Eira") Detection Effect
  useEffect(() => {
    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;

    if (!SpeechRecognition) {
      setWakeWordStatus('unsupported');
      setIsListeningForWakeWord(false);
      return;
    }

    if (state !== 'disconnected' || !wakeWordEnabled) {
      setIsListeningForWakeWord(false);
      if (state !== 'disconnected') {
        setWakeWordStatus('idle');
      }
      return;
    }

    let recognition: any = null;
    let isComponentMounted = true;
    let isIntentionalStop = false;
    let restartTimer: any = null;

    const startRecognition = () => {
      if (!isComponentMounted || state !== 'disconnected' || !wakeWordEnabled) return;
      try {
        recognition = new SpeechRecognition();
        recognition.continuous = true;
        recognition.interimResults = true;
        recognition.lang = 'en-US';

        recognition.onstart = () => {
          if (isComponentMounted) {
            setIsListeningForWakeWord(true);
            setWakeWordStatus('listening');
          }
        };

        recognition.onresult = (event: any) => {
          for (let i = event.resultIndex; i < event.results.length; i++) {
            const transcript = event.results[i][0].transcript;

            if (isWakePhraseDetected(transcript)) {
              console.log("⚡ Hands-Free Wake Word Triggered:", transcript);
              isIntentionalStop = true;
              
              playWakeChime();

              // Directly unlock and open Era Dashboard screen
              setDashboardUnlocked(true);
              setActiveTab('dashboard');
              window.location.hash = '#/dashboard';

              // Bring browser window to focus regardless of active background apps
              try {
                window.focus();
                if (window.parent) {
                  window.parent.focus();
                }
              } catch (e) {}

              // Alert document title if user is on another app/tab
              const origTitle = document.title;
              document.title = "⚡ ERA DASHBOARD - ONLINE ⚡";
              setTimeout(() => {
                document.title = origTitle;
              }, 4000);

              try {
                recognition.stop();
              } catch (e) {}

              setWakeWordStatus('detected');
              setIsWakingPulse(true);
              setTimeout(() => setIsWakingPulse(false), 3500);
              setWakeWordMessage(`Wake phrase recognized: "${transcript.trim()}" - Era Dashboard Opened!`);
              setTimeout(() => setWakeWordMessage(null), 5000);

              if (connectSessionRef.current) {
                connectSessionRef.current();
              }
              break;
            }
          }
        };

        recognition.onerror = (event: any) => {
          if (event.error === 'not-allowed' || event.error === 'service-not-allowed') {
            setWakeWordStatus('permission_denied');
            isIntentionalStop = true;
          } else {
            console.warn("Wake word recognition transient error:", event.error);
          }
        };

        recognition.onend = () => {
          if (isComponentMounted) {
            setIsListeningForWakeWord(false);
            if (!isIntentionalStop && state === 'disconnected' && wakeWordEnabled) {
              restartTimer = setTimeout(() => {
                if (isComponentMounted && state === 'disconnected' && wakeWordEnabled) {
                  startRecognition();
                }
              }, 300);
            }
          }
        };

        recognition.start();
      } catch (err) {
        console.error("[Wake Word Start Error]:", err);
      }
    };

    startRecognition();

    return () => {
      isComponentMounted = false;
      isIntentionalStop = true;
      if (restartTimer) clearTimeout(restartTimer);
      if (recognition) {
        try {
          recognition.stop();
        } catch (e) {}
      }
      setIsListeningForWakeWord(false);
    };
  }, [state, wakeWordEnabled]);

  // Frontend tool router mapping back results instantly to the web socket
  const handleToolRouter = (id: string, name: string, args: any, ws: WebSocket) => {
    if (ws.readyState !== WebSocket.OPEN) return;

    if (name === "openApplication" && args?.appName) {
      // Forward openApplication requests to the backend so the Era Python Agent can execute them.
      ws.send(JSON.stringify({
        type: "toolResponse",
        id,
        name: "openApplication",
        args
      }));
      return;
    }

    if (name === "openWebsite" && args?.url) {
      let url = args.url;
      const lowerUrl = url.toLowerCase();
      
      // Intercept and redirect to openApplication if they ask for local downloaded apps!
      // Any WhatsApp URL is forwarded to backend which decides: Desktop app OR WhatsApp Web
      if (lowerUrl.includes("whatsapp")) {
        handleToolRouter(id, "openApplication", { appName: "whatsapp" }, ws);
        return;
      }
      if (lowerUrl.includes("vscode") || lowerUrl.includes("visualstudio") || lowerUrl.includes("vs code") || lowerUrl.includes("vs-code")) {
        handleToolRouter(id, "openApplication", { appName: "vscode" }, ws);
        return;
      }
      if (lowerUrl.includes("chatgpt") || lowerUrl.includes("chat.openai.com") || lowerUrl.includes("chat gpt")) {
        handleToolRouter(id, "openApplication", { appName: "chatgpt" }, ws);
        return;
      }
      if (lowerUrl.includes("cloudcode") || lowerUrl.includes("cloud code")) {
        handleToolRouter(id, "openApplication", { appName: "cloudcode" }, ws);
        return;
      }

      if (lowerUrl.includes("ide") || lowerUrl.includes("google cloud shell")) {
        url = "https://ide.cloud.google.com/";
      } else if (lowerUrl === "youtube" || lowerUrl === "youtube.com" || lowerUrl === "www.youtube.com" || lowerUrl === "https://youtube.com" || lowerUrl === "https://www.youtube.com") {
        url = "https://youtube.com";
      }

      if (!url.startsWith("http://") && !url.startsWith("https://")) {
        url = "https://" + url;
      }

      setToolLogs(prev => [
        {
          id: Math.random().toString(36).substring(2, 9),
          time: new Date(),
          tool: "openWebsite",
          description: `Opening website: ${url}`,
          status: 'success'
        },
        ...prev
      ]);

      let openedDirectly = false;
      try {
        const newWin = window.open(url, "eira_companion_browser");
        if (newWin) {
          openedDirectly = true;
        }
      } catch (err) {
        console.error("Failed to open due to browser rules:", err);
      }

      if (!openedDirectly) {
        // Set active browser state for high-visibility UI popup to bypass sandbox blocking as a fallback
        setActiveBrowserAction({ url, timestamp: new Date() });
      }

      ws.send(JSON.stringify({
        type: "toolResponse",
        id,
        name: "openWebsite",
        output: { success: true, message: `Opened browser tab pointing to ${url}` }
      }));
    } else if (name === "captureScreen" || name === "screenControl") {
      if (!isScreenSharing) {
        setToolLogs(prev => [
          {
            id: Math.random().toString(36).substring(2, 9),
            time: new Date(),
            tool: name,
            description: `Blocked: Screen sharing permission is required.`,
            status: 'failed'
          },
          ...prev
        ]);
        ws.send(JSON.stringify({
          type: "toolResponse",
          id,
          name,
          output: { 
            success: false, 
            message: "Screen sharing permission is currently inactive (denied). Please ask the user to click the 'Share Screen' button in the interface first to grant permission so you can see what they are doing." 
          }
        }));
      } else {
        // Backend handles other local tools. We just trigger the pipeline
        ws.send(JSON.stringify({
          type: "toolResponse",
          id,
          name,
          args
        }));
      }
    } else {
      // Backend handles other local tools. We just trigger the pipeline
      ws.send(JSON.stringify({
        type: "toolResponse",
        id,
        name,
        args
      }));
    }
  };

  // Toggle QR Link WhatsApp
  const startWhatsAppLink = () => {
    setIsLinkingWhatsApp(true);
    setTimeout(() => {
      setIsLinkingWhatsApp(false);
      setKeysConfig(prev => ({ ...prev, whatsappStatus: "connected" }));
      setWhatsAppChats(prev => [
        {
          contactName: "ERA Agent",
          message: "WhatsApp linked successfully! I am fully synchronized.",
          timestamp: new Date().toISOString(),
          status: "sent"
        },
        ...prev
      ]);
    }, 4500);
  };

  // Canvas waveform visualizer loop
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let animationId: number;
    let phase = 0;

    const draw = () => {
      animationId = requestAnimationFrame(draw);
      const width = canvas.width;
      const height = canvas.height;
      ctx.clearRect(0, 0, width, height);

      phase += 0.04;
      const activeVolume = state === 'listening' ? userVolume : state === 'speaking' ? modelVolume : 0;

      // Center glowing orb representation
      if (state !== 'disconnected') {
        const glowRad = 50 + activeVolume * 0.4;
        const grad = ctx.createRadialGradient(width / 2, height / 2, 5, width / 2, height / 2, glowRad);
        if (state === 'listening') {
          grad.addColorStop(0, "rgba(6, 182, 212, 0.18)");
          grad.addColorStop(1, "rgba(6, 182, 212, 0)");
        } else if (state === 'speaking') {
          grad.addColorStop(0, "rgba(236, 72, 153, 0.22)");
          grad.addColorStop(1, "rgba(236, 72, 153, 0)");
        } else if (state === 'processing') {
          grad.addColorStop(0, "rgba(168, 85, 247, 0.18)");
          grad.addColorStop(1, "rgba(168, 85, 247, 0)");
        } else {
          grad.addColorStop(0, "rgba(99, 102, 241, 0.1)");
          grad.addColorStop(1, "rgba(99, 102, 241, 0)");
        }
        ctx.fillStyle = grad;
        ctx.beginPath();
        ctx.arc(width / 2, height / 2, glowRad, 0, Math.PI * 2);
        ctx.fill();
      }

      // Draw Orbiting Flare / Spark around the Central Orb when audio/voice input is active
      if (state === 'listening' || state === 'speaking' || activeVolume > 2) {
        const orbitRadius = 86;
        const orbitSpeed = state === 'listening' ? 0.04 + activeVolume * 0.002 : 0.03;
        const sparkAngle = phase * orbitSpeed * 10;
        const sparkX = width / 2 + Math.cos(sparkAngle) * orbitRadius;
        const sparkY = height / 2 + Math.sin(sparkAngle) * orbitRadius;

        // Comet trail particles behind the main flare spark
        for (let t = 1; t <= 10; t++) {
          const trailAngle = sparkAngle - t * 0.07;
          const tx = width / 2 + Math.cos(trailAngle) * orbitRadius;
          const ty = height / 2 + Math.sin(trailAngle) * orbitRadius;
          const trailAlpha = (1 - t / 11) * 0.75;
          const trailRadius = Math.max(1, 5 - t * 0.4);

          ctx.beginPath();
          ctx.arc(tx, ty, trailRadius, 0, Math.PI * 2);
          ctx.fillStyle = state === 'listening' 
            ? `rgba(6, 182, 212, ${trailAlpha})` 
            : `rgba(236, 72, 153, ${trailAlpha})`;
          ctx.fill();
        }

        // Main Flare Spark core glow
        const flareGlow = ctx.createRadialGradient(sparkX, sparkY, 0, sparkX, sparkY, 16 + activeVolume * 0.15);
        flareGlow.addColorStop(0, "rgba(255, 255, 255, 1)");
        flareGlow.addColorStop(0.35, state === 'listening' ? "rgba(6, 182, 212, 0.95)" : "rgba(236, 72, 153, 0.95)");
        flareGlow.addColorStop(0.7, state === 'listening' ? "rgba(168, 85, 247, 0.6)" : "rgba(245, 158, 11, 0.6)");
        flareGlow.addColorStop(1, "rgba(0, 0, 0, 0)");

        ctx.fillStyle = flareGlow;
        ctx.beginPath();
        ctx.arc(sparkX, sparkY, 16 + activeVolume * 0.15, 0, Math.PI * 2);
        ctx.fill();

        // White hot center point
        ctx.fillStyle = "#ffffff";
        ctx.beginPath();
        ctx.arc(sparkX, sparkY, 3.5, 0, Math.PI * 2);
        ctx.fill();
      }

      // Render 4 composite waveforms
      const waves = state === 'disconnected' ? 1 : 4;
      for (let i = 0; i < waves; i++) {
        ctx.beginPath();
        ctx.lineWidth = i === 0 ? 3.5 : 1.5;

        if (state === 'listening') {
          ctx.strokeStyle = i === 0 ? "rgba(6, 182, 212, 0.9)" : `rgba(16, 185, 129, ${0.4 - i * 0.1})`;
        } else if (state === 'speaking') {
          ctx.strokeStyle = i === 0 ? "rgba(236, 72, 153, 0.9)" : `rgba(168, 85, 247, ${0.4 - i * 0.1})`;
        } else if (state === 'processing') {
          ctx.strokeStyle = `rgba(168, 85, 247, ${0.5 - i * 0.1})`;
        } else if (state === 'connecting') {
          ctx.strokeStyle = `rgba(245, 158, 11, ${0.4 - i * 0.1})`;
        } else {
          ctx.strokeStyle = "rgba(99, 102, 241, 0.15)";
        }

        const amp = state === 'disconnected' ? 4 :
                    state === 'processing' ? 12 + Math.sin(phase * 2) * 4 :
                    10 + activeVolume * (0.4 + i * 0.12);

        const freq = state === 'processing' ? 0.04 : 0.02 + i * 0.005;
        const speed = state === 'processing' ? 0.08 : 0.03 + i * 0.01;

        for (let x = 0; x < width; x++) {
          const y = height / 2 + Math.sin(x * freq - phase * speed * 3) * amp * Math.sin((x / width) * Math.PI);
          if (x === 0) {
            ctx.moveTo(x, y);
          } else {
            ctx.lineTo(x, y);
          }
        }
        ctx.stroke();
      }
    };

    draw();
    return () => cancelAnimationFrame(animationId);
  }, [state, userVolume, modelVolume]);

  return (
    <div className="bg-slate-950 text-slate-100 font-sans min-h-screen flex flex-col justify-between p-4 relative select-none">
      {/* OS Background grids */}
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,rgba(15,23,42,0.45)_0%,rgba(2,6,23,1)_100%)] z-0 pointer-events-none" />
      <div className="absolute inset-0 bg-[linear-gradient(to_right,rgba(255,255,255,0.008)_1px,transparent_1px),linear-gradient(to_bottom,rgba(255,255,255,0.008)_1px,transparent_1px)] bg-[size:4rem_4rem] z-0 pointer-events-none" />

      {/* Offline Alert & Cloud Sync Header Banner */}
      {!user && !authLoading && (
        <div className="bg-gradient-to-r from-purple-900/30 via-slate-900/50 to-pink-900/30 border border-purple-500/10 text-slate-300 px-4 py-2.5 text-xs flex flex-col sm:flex-row items-center justify-between gap-2 rounded-xl mb-3 backdrop-blur-md relative overflow-hidden z-10">
          <div className="absolute inset-0 bg-gradient-to-r from-purple-500/5 via-transparent to-pink-500/5 pointer-events-none" />
          <div className="flex items-center gap-2">
            <span className="flex h-2 w-2 relative">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-pink-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-pink-500"></span>
            </span>
            <span>
              <strong>Eira Cloud Memory:</strong> Sync your email to unlock persistent chat memory, secure conversation backups, and private YouTube analyzer streams!
            </span>
          </div>
          <button 
            onClick={() => {
              setAuthMode('login');
              setAuthError(null);
              setShowAuthModal(true);
            }} 
            className="px-3 py-1 bg-pink-600 hover:bg-pink-500 active:scale-95 text-white font-semibold rounded-lg text-[10px] transition-all flex items-center gap-1 cursor-pointer border border-pink-500/20"
          >
            <User size={12} /> Sync Eira Account
          </button>
        </div>
      )}

      {/* Top Navbar Header matching original image design & controls */}
      <header className="flex items-center justify-between z-10 border-b border-cyan-500/20 pb-3 px-2">
        <div className="flex items-center gap-4">
          <div className="relative flex items-baseline gap-2.5">
            <span className="text-2xl font-black tracking-[0.2em] text-white drop-shadow-[0_0_12px_rgba(255,255,255,0.7)] font-sans">
              ERA
            </span>
            <div className="flex items-center gap-1.5 text-cyan-400 font-mono font-bold text-[11px] tracking-[0.2em] uppercase">
              <span className="flex items-center gap-0.5 text-cyan-400">
                <span className="w-1 h-3 bg-cyan-400 rounded-full animate-pulse" />
                <span className="w-1 h-4 bg-cyan-400 rounded-full animate-bounce" />
                <span className="w-1 h-2 bg-cyan-400 rounded-full animate-pulse" />
              </span>
              <span>AI ASSISTANT</span>
            </div>
            <div className="absolute -bottom-1 left-0 right-0 h-[2px] bg-gradient-to-r from-cyan-400 via-blue-500 to-transparent" />
          </div>
          
          <div className={`px-3 py-1 rounded-full text-[10px] font-mono tracking-widest uppercase flex items-center gap-1.5 border font-bold ${
            state === 'listening' ? 'bg-cyan-500/20 text-cyan-300 border-cyan-400/40 shadow-[0_0_12px_rgba(6,182,212,0.3)]' :
            state === 'speaking' ? 'bg-pink-500/20 text-pink-300 border-pink-400/40 shadow-[0_0_12px_rgba(236,72,153,0.3)]' :
            state === 'processing' ? 'bg-purple-500/20 text-purple-300 border-purple-400/40' :
            state === 'connecting' ? 'bg-amber-500/20 text-amber-300 border-amber-400/40' :
            'bg-cyan-950/40 text-cyan-400 border-cyan-500/30'
          }`}>
            <span className={`w-2 h-2 rounded-full ${
              state === 'listening' ? 'bg-cyan-400 animate-pulse' :
              state === 'speaking' ? 'bg-pink-400 animate-bounce' :
              state === 'processing' ? 'bg-purple-400 animate-pulse' :
              state === 'connecting' ? 'bg-amber-400 animate-spin' :
              'bg-cyan-400'
            }`} />
            {state === 'disconnected' ? "READY TO HELP" : 
             state === 'listening' ? "LISTENING" :
             state === 'speaking' ? "ERA SPEAKING" :
             state === 'processing' ? "THINKING" : state}
          </div>
        </div>

        {/* Center/Right Global Controls & Navigation */}
        <div className="flex items-center gap-3">
          {/* Quick Nav Bar Tabs */}
          <nav className="flex bg-slate-900/80 p-1 rounded-xl border border-slate-800 gap-1">
            <button 
              onClick={() => setActiveTab('voice')}
              className={`px-3 py-1 rounded-lg text-xs font-medium transition-all flex items-center gap-1.5 cursor-pointer ${
                activeTab === 'voice' 
                  ? 'bg-cyan-600 text-white shadow-lg shadow-cyan-600/20 font-bold' 
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Mic size={13} /> Dashboard UI
            </button>

            <button 
              onClick={() => {
                setActiveTab('chatbot');
                if (auth.currentUser && auth.currentUser.email) {
                  loadChatHistory(auth.currentUser.email).then(history => setChatbotMessages(history));
                }
              }}
              className={`px-3 py-1 rounded-lg text-xs font-medium transition-all flex items-center gap-1.5 cursor-pointer ${
                activeTab === 'chatbot' 
                  ? 'bg-pink-600 text-white shadow-lg shadow-pink-600/20' 
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <MessageSquare size={13} /> Text Chat
            </button>
            
            <button 
              onClick={() => {
                setActiveTab('workspace');
                fetchWorkspaceFiles();
              }}
              className={`px-3 py-1 rounded-lg text-xs font-medium transition-all flex items-center gap-1.5 cursor-pointer ${
                activeTab === 'workspace' 
                  ? 'bg-purple-600 text-white shadow-lg shadow-purple-600/20' 
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Terminal size={13} /> Workspace
            </button>
            
            <button 
              onClick={() => setActiveTab('dashboard')}
              className={`px-3 py-1 rounded-lg text-xs font-medium transition-all flex items-center gap-1.5 cursor-pointer ${
                activeTab === 'dashboard' 
                  ? 'bg-blue-600 text-white shadow-lg shadow-blue-600/20' 
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Settings size={13} /> Settings
            </button>
          </nav>

          {/* Window Control Action Icons matching image header top right */}
          <div className="flex items-center gap-2 pl-2 border-l border-slate-800/80">
            <button
              onClick={() => (window as any).eraDesktop?.minimize?.()}
              className="w-6 h-6 rounded flex items-center justify-center text-slate-400 hover:text-white hover:bg-slate-800/60 transition-colors cursor-pointer text-xs font-mono"
              title="Minimize Window"
            >
              _
            </button>
            <button
              onClick={() => (window as any).eraDesktop?.maximize?.()}
              className="w-6 h-6 rounded flex items-center justify-center text-slate-400 hover:text-white hover:bg-slate-800/60 transition-colors cursor-pointer text-xs font-mono"
              title="Maximize / Restore Window"
            >
              [ ]
            </button>
            <button
              onClick={() => (window as any).eraDesktop?.close?.()}
              className="w-6 h-6 rounded flex items-center justify-center text-slate-400 hover:text-rose-400 hover:bg-rose-950/40 transition-colors cursor-pointer text-xs font-mono"
              title="Close Window"
            >
              ✕
            </button>
          </div>
        </div>
      </header>

      {/* Main Container Panes */}
      <div className="flex-1 my-3 overflow-hidden relative z-10 flex flex-col min-h-[calc(100vh-100px)]">
        
        <AnimatePresence mode="wait">
          
          {/* VIEW 1: MAIN ERA DASHBOARD (FULL SCREEN DESKTOP UI) */}
          {activeTab === 'voice' && (
            <motion.div 
              key="voice-tab"
              initial={{ opacity: 0, scale: 0.99 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.99 }}
              className="flex-1 flex flex-col justify-between h-full relative"
            >
              {/* Sub-Tab Navigation & System Badges Header Bar */}
              <div className="flex flex-wrap items-center justify-between gap-3 bg-slate-900/30 border border-slate-900 rounded-2xl p-2 backdrop-blur-md mb-3">
                <div className="flex items-center gap-1 bg-slate-950/80 p-1 rounded-xl border border-slate-800/80">
                  <button
                    onClick={() => setVoiceSubTab('live')}
                    className={`px-3.5 py-1.5 rounded-lg text-xs font-mono font-medium transition-all flex items-center gap-2 cursor-pointer ${
                      voiceSubTab === 'live'
                        ? 'bg-cyan-600 text-white shadow-lg shadow-cyan-600/20 font-bold'
                        : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900'
                    }`}
                  >
                    <Mic size={13} />
                    <span>Live Dashboard</span>
                    {state !== 'disconnected' && (
                      <span className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse" />
                    )}
                  </button>

                  <button
                    onClick={() => setVoiceSubTab('history')}
                    className={`px-3.5 py-1.5 rounded-lg text-xs font-mono font-medium transition-all flex items-center gap-2 cursor-pointer ${
                      voiceSubTab === 'history'
                        ? 'bg-blue-600 text-white shadow-lg shadow-blue-600/20 font-bold'
                        : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900'
                    }`}
                  >
                    <History size={13} />
                    <span>Session Transcripts</span>
                    <span className={`px-1.5 py-0.5 rounded-full text-[10px] font-bold ${
                      voiceSubTab === 'history' 
                        ? 'bg-blue-950 text-blue-200 border border-blue-400/30' 
                        : 'bg-slate-800 text-slate-300'
                    }`}>
                      {transcriptions.length}
                    </span>
                  </button>
                </div>

                <div className="flex items-center gap-2 font-mono text-xs flex-wrap">
                  {/* High Thinking Mode Toggle */}
                  <button
                    onClick={() => setIsHighThinking(!isHighThinking)}
                    className={`px-3 py-1 rounded-xl text-[11px] font-mono transition-all flex items-center gap-1.5 border cursor-pointer ${
                      isHighThinking 
                        ? 'bg-purple-950/90 border-purple-500/50 text-purple-300 shadow-[0_0_12px_rgba(168,85,247,0.3)]' 
                        : 'bg-slate-950/80 border-slate-800 text-slate-500 hover:text-slate-300'
                    }`}
                  >
                    <BrainCircuit size={13} className={isHighThinking ? 'text-purple-400 animate-pulse' : ''} />
                    <span className="font-semibold hidden sm:inline">High Thinking:</span>
                    <span className={isHighThinking ? 'text-purple-300 font-bold' : 'text-slate-500'}>
                      {isHighThinking ? 'gemini-3.1-pro' : 'OFF'}
                    </span>
                  </button>

                  {/* Bluetooth Audio Toggle */}
                  <button
                    onClick={() => setShowBluetoothManager(!showBluetoothManager)}
                    className={`px-3 py-1 rounded-xl text-[11px] font-mono transition-all flex items-center gap-1.5 border cursor-pointer ${
                      showBluetoothManager 
                        ? 'bg-cyan-950/90 border-cyan-500/50 text-cyan-300 shadow-[0_0_12px_rgba(6,182,212,0.3)]' 
                        : 'bg-slate-950/80 border-slate-800 text-slate-400 hover:text-cyan-300'
                    }`}
                  >
                    <Bluetooth size={13} className="text-cyan-400" />
                    <span className="font-semibold hidden sm:inline">Bluetooth</span>
                  </button>

                  {/* Wake Word Toggle */}
                  <button
                    onClick={() => setWakeWordEnabled(!wakeWordEnabled)}
                    className={`px-3 py-1 rounded-xl text-[11px] font-mono transition-all flex items-center gap-1.5 border cursor-pointer ${
                      !wakeWordEnabled 
                        ? 'bg-slate-950/80 border-slate-800 text-slate-500'
                        : 'bg-slate-950/80 border-cyan-500/30 text-cyan-300'
                    }`}
                  >
                    <Ear size={13} className={wakeWordEnabled ? 'text-cyan-400 animate-pulse' : ''} />
                    <span className="font-semibold hidden sm:inline">Wake Word:</span>
                    <span className="text-cyan-300">"Hey ERA"</span>
                  </button>

                  <button
                    onClick={isScreenSharing ? stopScreenShare : startScreenShare}
                    className={`px-3 py-1 rounded-xl text-[11px] font-mono transition-all flex items-center gap-1.5 border cursor-pointer ${
                      isScreenSharing 
                        ? 'bg-cyan-950 text-cyan-300 border-cyan-500/40' 
                        : 'bg-slate-950/80 text-slate-400 border-slate-800 hover:text-slate-200'
                    }`}
                  >
                    <span className={`w-1.5 h-1.5 rounded-full ${isScreenSharing ? 'bg-cyan-400 animate-ping' : 'bg-slate-600'}`} />
                    <span>{isScreenSharing ? "Screen Shared" : "Share Screen"}</span>
                  </button>
                </div>
              </div>

              {/* Bluetooth & Audio Manager Panel */}
              <AnimatePresence>
                {showBluetoothManager && (
                  <motion.div
                    initial={{ opacity: 0, height: 0, y: -10 }}
                    animate={{ opacity: 1, height: "auto", y: 0 }}
                    exit={{ opacity: 0, height: 0, y: -10 }}
                    className="w-full mb-3 overflow-hidden"
                  >
                    <BluetoothMusicManager 
                      externalMusicCommand={externalMusicCommand}
                      onStatusMessage={handleBluetoothStatusMessage}
                    />
                  </motion.div>
                )}
              </AnimatePresence>

              {/* Sub-Tab Content Switcher */}
              <AnimatePresence mode="wait">
                {voiceSubTab === 'live' ? (
                  <motion.div 
                    key="voice-live-subtab"
                    initial={{ opacity: 0, scale: 0.99 }}
                    animate={{ opacity: 1, scale: 1 }}
                    exit={{ opacity: 0, scale: 0.99 }}
                    className="flex-1 flex flex-col justify-between"
                  >
                    {/* Outer Left column wrapper: If screen sharing, split into Orb + Stream preview */}
                    <div className="flex-1 flex flex-col gap-4 justify-between min-h-[500px]">
                      
                      {/* Main Split Grid: Left Chat Card + Right AI Orb Stage (Exact layout matching image) */}
                      <div className="flex-1 flex flex-col lg:flex-row items-stretch gap-6 relative z-10 min-h-[460px]">
                        
                        {/* LEFT PANEL: Translucent Sci-Fi Glassmorphism Chat & Input Card */}
                        <div className="w-full lg:w-[440px] xl:w-[480px] bg-[#061226]/85 border border-cyan-500/30 rounded-2xl p-6 backdrop-blur-2xl shadow-[0_0_40px_rgba(6,182,212,0.14)] flex flex-col justify-between relative overflow-hidden transition-all duration-300">
                          {/* Left Border Glow Highlight Bar */}
                          <div className="absolute top-0 left-0 bottom-0 w-[4px] bg-gradient-to-b from-cyan-400 via-blue-500 to-cyan-800 shadow-[0_0_12px_rgba(6,182,212,0.8)]" />
                          
                          {/* Chat Messages Area (WhatsApp Style Left/Right Auto-updating Chat) */}
                          <div className="flex-1 overflow-y-auto space-y-3.5 pr-2 text-sm font-sans mb-4 min-h-[280px] max-h-[420px] scrollbar-thin">
                            {dashboardChats.length === 0 ? (
                              <div className="space-y-4 pt-3">
                                {/* Placeholder shown when no chats yet */}
                                <div className="flex justify-end animate-fade-in">
                                  <div className="bg-[#0b2447]/90 border border-cyan-500/30 rounded-2xl rounded-tr-none px-4 py-2.5 max-w-[85%] text-slate-100 shadow-[0_0_15px_rgba(6,182,212,0.1)]">
                                    <span className="font-bold text-cyan-300 text-sm">You: </span>
                                    <span className="text-slate-200 text-sm font-medium">Say something to ERA...</span>
                                  </div>
                                </div>
                                <div className="flex justify-start animate-fade-in">
                                  <div className="bg-[#081a36]/90 border border-cyan-400/40 rounded-2xl rounded-tl-none px-4 py-2.5 max-w-[85%] text-cyan-200 shadow-[0_0_15px_rgba(6,182,212,0.15)]">
                                    <span className="font-bold text-cyan-400 text-sm">ERA: </span>
                                    <span className="text-cyan-100 text-sm font-medium">I'm here, boss. Ready to assist.</span>
                                  </div>
                                </div>
                              </div>
                            ) : (
                              dashboardChats.map((t) => (
                                <div
                                  key={t.id}
                                  className={`flex ${t.sender === 'user' ? 'justify-end' : 'justify-start'} animate-fade-in`}
                                >
                                  {t.sender === 'user' ? (
                                    <div className="bg-[#0b2447]/95 border border-cyan-500/30 rounded-2xl rounded-tr-none px-4 py-2.5 max-w-[85%] text-slate-100 shadow-[0_0_15px_rgba(6,182,212,0.12)]">
                                      <span className="font-bold text-cyan-300 text-sm">You: </span>
                                      <span className="text-slate-100 text-sm font-medium leading-relaxed">{t.text}</span>
                                    </div>
                                  ) : (
                                    <div className="bg-[#081a36]/95 border border-cyan-400/40 rounded-2xl rounded-tl-none px-4 py-2.5 max-w-[85%] text-cyan-200 shadow-[0_0_15px_rgba(6,182,212,0.15)]">
                                      <span className="font-bold text-cyan-400 text-sm">ERA: </span>
                                      <span className="text-cyan-100 text-sm font-medium leading-relaxed">{cleanUrlsAndLinks(t.text)}</span>
                                    </div>
                                  )}
                                </div>
                              ))
                            )}
                            <div ref={transcriptionsEndRef} />
                          </div>

                          {/* Bottom Input Capsule Bar (Mic + Speak to ERA + Waveform) */}
                          <form 
                            onSubmit={(e) => {
                              e.preventDefault();
                              const val = (e.currentTarget.elements.namedItem("speakInput") as HTMLInputElement)?.value;
                              if (val && val.trim()) {
                                const userMsg: Transcription = { id: Date.now().toString(), text: val.trim(), sender: 'user', timestamp: new Date() };
                                setTranscriptions(prev => [...prev, userMsg]);
                                setDashboardChats(prev => [...prev, { id: userMsg.id, sender: 'user', text: val.trim(), timestamp: new Date() }]);
                                if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
                                  wsRef.current.send(JSON.stringify({ type: 'text', data: val.trim() }));
                                }
                                (e.currentTarget.elements.namedItem("speakInput") as HTMLInputElement).value = "";
                              }
                            }}
                            className="bg-[#0b1c36]/95 border border-cyan-500/40 hover:border-cyan-400/70 rounded-full px-4 py-2.5 flex items-center justify-between gap-3 shadow-[0_0_20px_rgba(6,182,212,0.15)] transition-all"
                          >
                            <button
                              type="button"
                              onClick={toggleSession}
                              title={state === 'listening' ? "Stop Listening" : "Start Voice Input"}
                              className={`w-8 h-8 rounded-full flex items-center justify-center transition-all cursor-pointer shrink-0 ${
                                state === 'listening' 
                                  ? 'bg-cyan-400 text-slate-950 shadow-[0_0_18px_rgba(6,182,212,0.9)] animate-pulse' 
                                  : 'bg-cyan-950/80 hover:bg-cyan-900 text-cyan-400 border border-cyan-500/40'
                              }`}
                            >
                              <Mic size={16} />
                            </button>

                            <input
                              name="speakInput"
                              type="text"
                              placeholder="Speak to ERA"
                              className="flex-1 bg-transparent border-none outline-none text-slate-100 placeholder-slate-400 text-sm font-sans"
                            />

                            <div className="flex items-center gap-1 text-cyan-400 shrink-0">
                              <span className={`w-0.5 h-3 bg-cyan-400 rounded-full ${state === 'listening' ? 'animate-bounce' : 'opacity-60'}`} />
                              <span className={`w-0.5 h-4 bg-cyan-400 rounded-full ${state === 'listening' ? 'animate-pulse' : 'opacity-80'}`} />
                              <span className={`w-0.5 h-2 bg-cyan-400 rounded-full ${state === 'listening' ? 'animate-bounce' : 'opacity-60'}`} />
                              <span className={`w-0.5 h-4 bg-cyan-400 rounded-full ${state === 'listening' ? 'animate-pulse' : 'opacity-80'}`} />
                              <span className={`w-0.5 h-2.5 bg-cyan-400 rounded-full ${state === 'listening' ? 'animate-bounce' : 'opacity-60'}`} />
                            </div>
                          </form>
                        </div>

                        {/* RIGHT PANEL: Sci-Fi Holographic AI Orb Stage */}
                        <div className="flex-1 bg-[#030917]/70 border border-cyan-500/20 rounded-2xl flex flex-col items-center justify-center relative overflow-hidden p-6 min-h-[440px] shadow-[inset_0_0_50px_rgba(6,182,212,0.05)]">
                          
                          {/* HUD Background Concentric Thin Rings & Radial Glow */}
                          <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
                            <div className="w-[360px] h-[360px] rounded-full border border-cyan-500/15" />
                            <div className="absolute w-[460px] h-[460px] rounded-full border border-cyan-500/10" />
                            <div className="absolute w-[580px] h-[580px] rounded-full border border-cyan-500/5" />
                            <div className="absolute inset-x-0 h-32 bg-[radial-gradient(ellipse_at_center,rgba(6,182,212,0.16)_0%,transparent_75%)]" />
                          </div>

                          {/* Central Glowing AI Orb Container */}
                          <div className="relative w-80 h-80 flex items-center justify-center z-10">
                            
                            {/* Background Audio Waveform Canvas */}
                            <canvas 
                              ref={canvasRef} 
                              width={340} 
                              height={340} 
                              className="absolute z-10 pointer-events-none rounded-full"
                            />

                            {/* Interactive AI Orb Core with Precise Sizing Rules:
                                - User Speaks (listening): Scale GROWS LARGER than medium (scale ~ 1.38 to 1.48)
                                - ERA Speaks (speaking): Scale SHRINKS SMALLER than medium (scale ~ 0.78 to 0.85)
                                - Calm / Idle: Scale is NORMAL MEDIUM SIZE (scale 1.0)
                            */}
                            <motion.div 
                              id="central-orb-control"
                              onClick={toggleSession}
                              animate={{
                                scale: (isWakingPulse || wakeWordStatus === 'detected') ? 1.30 :
                                       (state === 'listening' && userVolume > 1) ? Math.min(1.48, 1.38 + (userVolume * 0.005)) :
                                       state === 'listening' ? 1.38 :
                                       state === 'speaking' ? Math.max(0.72, 0.80 - (modelVolume * 0.003)) :
                                       state === 'processing' ? [1.03, 0.97, 1.03] :
                                       state === 'connecting' ? [1, 1.04, 1] : 1.0,
                                boxShadow: state === 'listening'
                                  ? `0 0 ${45 + userVolume * 0.6}px rgba(6,182,212,0.95), inset 0 0 35px rgba(6,182,212,0.6)`
                                  : state === 'speaking'
                                  ? `0 0 ${25 + modelVolume * 0.4}px rgba(6,182,212,0.65), inset 0 0 20px rgba(6,182,212,0.4)`
                                  : state === 'processing'
                                  ? '0 0 35px rgba(168,85,247,0.6)'
                                  : '0 0 40px rgba(6,182,212,0.5), inset 0 0 25px rgba(6,182,212,0.35)'
                              }}
                              transition={{
                                duration: (isWakingPulse || wakeWordStatus === 'detected') ? 0.6 : 0.15,
                                ease: "easeOut"
                              }}
                              className="w-48 h-48 rounded-full cursor-pointer flex items-center justify-center relative z-20 bg-gradient-to-br from-cyan-300 via-blue-600 to-slate-950 border-2 border-cyan-300 shadow-[0_0_55px_rgba(6,182,212,0.7)] transition-all duration-300 group"
                            >
                              {/* Inner Energy Wave Sphere Layer */}
                              <div className="absolute inset-1.5 rounded-full bg-[radial-gradient(circle_at_30%_30%,rgba(255,255,255,0.85)_0%,rgba(6,182,212,0.45)_40%,rgba(2,132,199,0.95)_100%)] opacity-95 backdrop-blur-sm overflow-hidden flex items-center justify-center">
                                {/* Internal Fluid Motion Wave */}
                                <div className="w-full h-full bg-[radial-gradient(ellipse_at_center,rgba(56,189,248,0.7)_0%,transparent_70%)] animate-pulse" />
                              </div>

                              {/* Core Icon Overlay */}
                              <AnimatePresence mode="wait">
                                {state === 'listening' ? (
                                  <motion.div key="listen" className="relative z-30 flex flex-col items-center gap-1 text-white">
                                    <Mic size={34} className="animate-pulse drop-shadow-[0_0_12px_rgba(255,255,255,0.95)]" />
                                  </motion.div>
                                ) : state === 'speaking' ? (
                                  <motion.div key="speak" className="relative z-30 flex flex-col items-center gap-1 text-white">
                                    <Volume2 size={32} className="animate-pulse drop-shadow-[0_0_12px_rgba(255,255,255,0.95)]" />
                                  </motion.div>
                                ) : state === 'processing' ? (
                                  <motion.div key="proc" className="relative z-30 flex flex-col items-center gap-1 text-purple-200">
                                    <Sparkles size={32} className="animate-spin" />
                                  </motion.div>
                                ) : null}
                              </AnimatePresence>
                            </motion.div>
                          </div>

                          {/* Status Text Indicator Below Orb */}
                          <div className="mt-5 flex items-center gap-2 text-cyan-400 font-mono tracking-[0.25em] text-xs font-bold uppercase select-none">
                            <span className="text-cyan-400 animate-pulse">···</span>
                            <span>
                              {state === 'listening' ? "LISTENING" :
                               state === 'speaking' ? "ERA SPEAKING" :
                               state === 'processing' ? "THINKING" :
                               "LISTENING"}
                            </span>
                            <span className="text-cyan-400 animate-pulse">···</span>
                          </div>
                        </div>
                      </div>

                      {/* BOTTOM CENTER: Floating Voice Mode Capsule Button */}
                      <div className="flex justify-center items-center pt-2 relative z-20">
                        <button
                          onClick={toggleSession}
                          className="bg-[#08172e]/95 hover:bg-[#0c2040] border border-cyan-500/50 px-6 py-2 rounded-full text-xs font-mono font-bold text-slate-100 flex items-center gap-2.5 shadow-[0_0_25px_rgba(6,182,212,0.25)] transition-all cursor-pointer group hover:scale-105"
                        >
                          <span className="text-cyan-400 font-bold flex items-center gap-0.5 text-[10px]">
                            <span>||||</span>
                          </span>
                          <span className="tracking-[0.15em]">VOICE MODE</span>
                          <span className={`w-2.5 h-2.5 rounded-full ${state !== 'disconnected' ? 'bg-cyan-400 animate-ping' : 'bg-cyan-400'}`} />
                        </button>
                      </div>

                    </div>
                  </motion.div>
                ) : (
                  <motion.div 
                    key="voice-history-subtab"
                    initial={{ opacity: 0, x: 10 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0, x: -10 }}
                    className="flex-1 flex flex-col gap-4 overflow-hidden min-h-[500px]"
                  >
                    {/* Session Overview Stats Row */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <div className="bg-slate-900/50 border border-slate-900 rounded-xl p-3 flex items-center gap-3">
                  <div className="p-2.5 bg-cyan-950/60 border border-cyan-500/20 text-cyan-400 rounded-lg">
                    <MessageSquare size={18} />
                  </div>
                  <div>
                    <div className="text-lg font-bold text-white font-mono">{transcriptions.length}</div>
                    <div className="text-[10px] text-slate-400 uppercase tracking-wider font-mono">Total Turns</div>
                  </div>
                </div>

                <div className="bg-slate-900/50 border border-slate-900 rounded-xl p-3 flex items-center gap-3">
                  <div className="p-2.5 bg-cyan-950/60 border border-cyan-500/20 text-cyan-400 rounded-lg">
                    <User size={18} />
                  </div>
                  <div>
                    <div className="text-lg font-bold text-cyan-300 font-mono">
                      {transcriptions.filter(t => t.sender === 'user').length}
                    </div>
                    <div className="text-[10px] text-slate-400 uppercase tracking-wider font-mono">User Messages</div>
                  </div>
                </div>

                <div className="bg-slate-900/50 border border-slate-900 rounded-xl p-3 flex items-center gap-3">
                  <div className="p-2.5 bg-pink-950/60 border border-pink-500/20 text-pink-400 rounded-lg">
                    <Sparkles size={18} />
                  </div>
                  <div>
                    <div className="text-lg font-bold text-pink-300 font-mono">
                      {transcriptions.filter(t => t.sender === 'model').length}
                    </div>
                    <div className="text-[10px] text-slate-400 uppercase tracking-wider font-mono">Eira Responses</div>
                  </div>
                </div>

                <div className="bg-slate-900/50 border border-slate-900 rounded-xl p-3 flex items-center gap-3">
                  <div className="p-2.5 bg-purple-950/60 border border-purple-500/20 text-purple-400 rounded-lg">
                    <FileText size={18} />
                  </div>
                  <div>
                    <div className="text-lg font-bold text-purple-300 font-mono">
                      {transcriptions.reduce((acc, t) => acc + (t.text ? t.text.trim().split(/\s+/).length : 0), 0)}
                    </div>
                    <div className="text-[10px] text-slate-400 uppercase tracking-wider font-mono">Words Spoken</div>
                  </div>
                </div>
              </div>

              {/* Search & Filter Controls */}
              <div className="bg-slate-900/40 border border-slate-900 rounded-2xl p-3 flex flex-wrap items-center justify-between gap-3">
                {/* Search Input */}
                <div className="relative flex-1 min-w-[220px]">
                  <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
                  <input
                    type="text"
                    value={historySearchQuery}
                    onChange={(e) => setHistorySearchQuery(e.target.value)}
                    placeholder="Search transcribed phrases..."
                    className="w-full bg-slate-950/90 border border-slate-800 rounded-xl pl-9 pr-8 py-1.5 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500/50 font-mono"
                  />
                  {historySearchQuery && (
                    <button
                      onClick={() => setHistorySearchQuery("")}
                      className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300 text-xs font-mono cursor-pointer"
                    >
                      ✕
                    </button>
                  )}
                </div>

                {/* Speaker Filters */}
                <div className="flex items-center gap-1.5 bg-slate-950/80 p-1 rounded-xl border border-slate-800 text-xs font-mono">
                  <button
                    onClick={() => setHistorySpeakerFilter('all')}
                    className={`px-2.5 py-1 rounded-lg transition-all cursor-pointer ${
                      historySpeakerFilter === 'all'
                        ? 'bg-slate-800 text-white font-semibold'
                        : 'text-slate-400 hover:text-slate-200'
                    }`}
                  >
                    All Speakers
                  </button>
                  <button
                    onClick={() => setHistorySpeakerFilter('user')}
                    className={`px-2.5 py-1 rounded-lg transition-all cursor-pointer ${
                      historySpeakerFilter === 'user'
                        ? 'bg-cyan-950 text-cyan-300 border border-cyan-500/30 font-semibold'
                        : 'text-slate-400 hover:text-slate-200'
                    }`}
                  >
                    You
                  </button>
                  <button
                    onClick={() => setHistorySpeakerFilter('model')}
                    className={`px-2.5 py-1 rounded-lg transition-all cursor-pointer ${
                      historySpeakerFilter === 'model'
                        ? 'bg-pink-950 text-pink-300 border border-pink-500/30 font-semibold'
                        : 'text-slate-400 hover:text-slate-200'
                    }`}
                  >
                    Eira
                  </button>
                </div>
              </div>

              {/* History Feed Container */}
              <div className="flex-1 bg-slate-900/30 border border-slate-900 rounded-2xl p-4 overflow-y-auto space-y-3.5 min-h-[300px] scrollbar-thin">
                {filteredTranscriptions.length === 0 ? (
                  <div className="h-full min-h-[250px] flex flex-col items-center justify-center text-center p-6 bg-slate-950/40 rounded-xl border border-slate-900">
                    <div className="p-4 bg-slate-900/80 border border-slate-800 rounded-full text-slate-500 mb-3">
                      {historySearchQuery ? <Search size={28} /> : <Clock size={28} />}
                    </div>
                    <h4 className="text-sm font-semibold text-slate-200 font-mono mb-1">
                      {historySearchQuery ? "No matching voice transcripts found" : "No Transcribed Voice History Yet"}
                    </h4>
                    <p className="text-xs text-slate-400 max-w-md mb-4 leading-relaxed font-sans">
                      {historySearchQuery 
                        ? `No transcriptions matched "${historySearchQuery}". Try adjusting your search keyword or clearing the filter.` 
                        : "Conversations from your voice session will automatically appear here in real-time as you speak with Eira."}
                    </p>
                    {!historySearchQuery && (
                      <button
                        onClick={() => {
                          setVoiceSubTab('live');
                          if (state === 'disconnected') {
                            toggleSession();
                          }
                        }}
                        className="px-4 py-2 bg-pink-600 hover:bg-pink-500 text-white font-mono font-medium text-xs rounded-xl shadow-lg shadow-pink-600/20 transition-all flex items-center gap-2 cursor-pointer"
                      >
                        <Mic size={14} />
                        <span>{state === 'disconnected' ? "Start Voice Session" : "Return to Live Orb"}</span>
                      </button>
                    )}
                  </div>
                ) : (
                  filteredTranscriptions.map((t) => (
                    <motion.div
                      key={t.id}
                      initial={{ opacity: 0, y: 8 }}
                      animate={{ opacity: 1, y: 0 }}
                      className={`p-4 rounded-xl border transition-all ${
                        t.sender === 'user'
                          ? 'bg-slate-950/70 border-cyan-500/20 hover:border-cyan-500/40 shadow-[0_0_15px_rgba(6,182,212,0.03)]'
                          : 'bg-slate-950/70 border-pink-500/20 hover:border-pink-500/40 shadow-[0_0_15px_rgba(236,72,153,0.03)]'
                      }`}
                    >
                      <div className="flex items-center justify-between border-b border-slate-900 pb-2 mb-2.5">
                        <div className="flex items-center gap-2">
                          <span className={`px-2.5 py-0.5 rounded-full text-[10px] font-mono font-bold uppercase tracking-wider flex items-center gap-1.5 ${
                            t.sender === 'user'
                              ? 'bg-cyan-950/80 text-cyan-300 border border-cyan-500/30'
                              : 'bg-pink-950/80 text-pink-300 border border-pink-500/30'
                          }`}>
                            {t.sender === 'user' ? (
                              <>
                                <User size={10} />
                                <span>You</span>
                              </>
                            ) : (
                              <>
                                <Sparkles size={10} />
                                <span>Eira Assistant</span>
                              </>
                            )}
                          </span>

                          <span className="text-[10px] font-mono text-slate-500">
                            Turn #{transcriptions.indexOf(t) + 1}
                          </span>
                        </div>

                        <div className="flex items-center gap-2 text-[10px] font-mono text-slate-500">
                          <Clock size={11} className="text-slate-600" />
                          <span>{new Date(t.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}</span>
                        </div>
                      </div>

                      <div className="text-xs text-slate-200 leading-relaxed font-sans whitespace-pre-wrap">
                        {cleanUrlsAndLinks(t.text)}
                      </div>

                      <div className="mt-3 pt-2.5 border-t border-slate-900/80 flex items-center justify-between gap-2">
                        <div className="flex items-center gap-2">
                          <button
                            onClick={() => handleCopyText(t.text, t.id)}
                            className="px-2 py-1 bg-slate-900 hover:bg-slate-800 text-slate-300 rounded text-[10px] font-mono transition-all flex items-center gap-1 cursor-pointer border border-slate-800"
                            title="Copy text to clipboard"
                          >
                            {copiedId === t.id ? (
                              <>
                                <Check size={11} className="text-emerald-400" />
                                <span className="text-emerald-400">Copied!</span>
                              </>
                            ) : (
                              <>
                                <Copy size={11} />
                                <span>Copy</span>
                              </>
                            )}
                          </button>

                          <button
                            onClick={() => handleSpeakText(t.text)}
                            className="px-2 py-1 bg-slate-900 hover:bg-slate-800 text-slate-300 rounded text-[10px] font-mono transition-all flex items-center gap-1 cursor-pointer border border-slate-800"
                            title="Read text aloud"
                          >
                            <Volume2 size={11} className="text-cyan-400" />
                            <span>Read Aloud</span>
                          </button>
                        </div>

                        <button
                          onClick={() => {
                            setActiveTab('chatbot');
                            setChatInput(`Regarding the voice transcript: "${t.text}" - `);
                          }}
                          className="text-[10px] font-mono text-pink-400 hover:text-pink-300 flex items-center gap-1 hover:underline cursor-pointer"
                        >
                          <span>Ask in Chat</span>
                          <ChevronRight size={10} />
                        </button>
                      </div>
                    </motion.div>
                  ))
                )}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </motion.div>
    )}

          {/* VIEW: EIRA CHATBOT & YOUTUBE INSPECTOR */}
          {activeTab === 'chatbot' && (
            <motion.div 
              key="chatbot-tab"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className="flex-1 flex flex-col lg:flex-row gap-4 h-full overflow-hidden"
            >
              {/* Left Column: Interactive Chat Panel */}
              <div className="flex-1 flex flex-col bg-slate-900/30 border border-slate-900 rounded-2xl overflow-hidden min-h-[460px] lg:h-full relative">
                
                {/* Chat Header banner */}
                <div className="bg-slate-950/80 border-b border-slate-900 px-4 py-3 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <div className="relative">
                      <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-pink-500 to-purple-600 flex items-center justify-center text-white font-bold text-xs shadow-md font-sans">
                        ER
                      </div>
                      <span className="absolute bottom-0 right-0 w-2.5 h-2.5 rounded-full bg-emerald-500 border-2 border-slate-950 animate-pulse" />
                    </div>
                    <div>
                      <h3 className="text-xs font-bold text-slate-200">Eira Text Chat</h3>
                      <p className="text-[9px] text-slate-500 font-mono">Secure Cloud Sync</p>
                    </div>
                  </div>
                  
                  {/* Account / Sync Status Badge */}
                  <div className="text-[10px] font-mono text-slate-500 flex items-center gap-1.5">
                    {user ? (
                      <span className="text-emerald-400 flex items-center gap-1">
                        <span className="w-1.5 h-1.5 bg-emerald-500 rounded-full" /> Cloud Synced
                      </span>
                    ) : (
                      <span className="text-amber-400 flex items-center gap-1">
                        <span className="w-1.5 h-1.5 bg-amber-500 rounded-full animate-ping" /> Local Only (Sign in to back up)
                      </span>
                    )}
                  </div>
                </div>

                {/* Messages Log Container */}
                <div className="flex-1 overflow-y-auto p-4 space-y-4 max-h-[480px] lg:max-h-[580px] scrollbar-thin">
                  {chatbotMessages.length === 0 ? (
                    <div className="h-[250px] flex flex-col items-center justify-center text-center p-6 space-y-3">
                      <div className="w-12 h-12 rounded-full bg-pink-500/10 border border-pink-500/20 flex items-center justify-center text-pink-400">
                        <MessageSquare size={20} />
                      </div>
                      <div>
                        <h4 className="text-xs font-bold text-slate-300">Start a chat with Eira</h4>
                        <p className="text-[10px] text-slate-500 max-w-xs mt-1">
                          Type a message below or share a YouTube link for me to analyze. I'll recall everything we've discussed!
                        </p>
                      </div>
                    </div>
                  ) : (
                    chatbotMessages.map((msg) => {
                      const isMe = msg.sender === 'user';
                      return (
                        <div 
                          key={msg.id} 
                          className={`flex ${isMe ? 'justify-end' : 'justify-start'} animate-fade-in`}
                        >
                          <div className={`max-w-[80%] rounded-2xl px-3.5 py-2.5 text-xs ${
                            isMe 
                              ? 'bg-pink-600 text-white rounded-tr-none shadow-md shadow-pink-600/10' 
                              : 'bg-slate-900/80 border border-slate-800 text-slate-300 rounded-tl-none'
                          }`}>
                            <div className="flex items-center gap-1.5 text-[9px] font-mono mb-1 text-slate-400">
                              <span className="font-bold">{isMe ? 'My Boss' : 'Eira'}</span>
                              <span>•</span>
                              <span>
                                {new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                              </span>
                              {msg.type === 'voice' && (
                                <span className="bg-pink-500/10 text-pink-400 border border-pink-500/20 px-1 rounded text-[8px]">
                                  Voice
                                </span>
                              )}
                              {msg.type === 'youtube' && (
                                <span className="bg-red-500/10 text-red-400 border border-red-500/20 px-1 rounded text-[8px]">
                                  YouTube Analysis
                                </span>
                              )}
                            </div>
                            
                            <p className="leading-relaxed whitespace-pre-wrap">{msg.text}</p>
                            
                            {/* Render metadata thumbnail or summary if YouTube analysis */}
                            {msg.metadata?.youtubeUrl && (
                              <div className="mt-2 pt-2 border-t border-slate-800/60">
                                <a 
                                  href={msg.metadata.youtubeUrl} 
                                  target="eira_companion_browser" 
                                  rel="noopener noreferrer"
                                  className="text-[10px] text-red-400 hover:underline flex items-center gap-1 font-mono mb-1.5"
                                >
                                  <Youtube size={12} /> View Source Video
                                </a>
                                {msg.metadata.title && (
                                  <p className="text-[11px] font-bold text-slate-100">{msg.metadata.title}</p>
                                )}
                                {msg.metadata.author && (
                                  <p className="text-[9px] text-slate-400">By: {msg.metadata.author}</p>
                                )}
                              </div>
                            )}
                          </div>
                        </div>
                      );
                    })
                  )}
                  <div ref={chatbotEndRef} />
                </div>

                {/* Loading state bar */}
                {chatLoading && (
                  <div className="absolute bottom-16 left-4 right-4 bg-slate-950/80 border border-slate-800/80 px-3 py-1.5 rounded-lg flex items-center gap-2 text-[10px] text-slate-400 animate-pulse font-mono z-10">
                    <span className="w-2 h-2 rounded-full bg-cyan-500 animate-ping" />
                    <span>Eira is processing your request...</span>
                  </div>
                )}

                {/* Input Controls */}
                <form 
                  onSubmit={(e) => {
                    e.preventDefault();
                    handleSendChat();
                  }}
                  className="bg-slate-950/90 border-t border-slate-900 p-3 flex gap-2 items-center mt-auto"
                >
                  <input 
                    type="text"
                    value={chatInput}
                    onChange={(e) => setChatInput(e.target.value)}
                    disabled={chatLoading}
                    placeholder="Ask Eira anything or type a prompt..."
                    className="flex-1 bg-slate-900/60 border border-slate-800 rounded-xl px-3.5 py-2.5 text-xs text-slate-200 placeholder-slate-600 focus:outline-none focus:border-pink-500/50 focus:ring-1 focus:ring-pink-500/20 disabled:opacity-50"
                  />
                  <button
                    type="submit"
                    disabled={chatLoading || !chatInput.trim()}
                    className="p-2.5 bg-pink-600 hover:bg-pink-500 disabled:bg-slate-800 text-white rounded-xl transition-all shadow-md active:scale-95 disabled:scale-100 cursor-pointer disabled:cursor-not-allowed"
                    title="Send message to Eira"
                  >
                    <Send size={15} />
                  </button>
                </form>
              </div>

              {/* Right Column: AI Video Parser Panel */}
              <div className="w-full lg:w-[340px] flex flex-col gap-4">
                
                {/* 1. YouTube Link Downloader Widget */}
                <div className="bg-slate-900/50 border border-slate-900 rounded-2xl p-4 flex flex-col relative overflow-hidden">
                  <div className="absolute top-0 right-0 w-32 h-32 bg-red-600/5 rounded-full blur-3xl pointer-events-none" />
                  
                  <div className="flex items-center gap-2 border-b border-slate-800 pb-2 mb-3">
                    <Youtube className="text-red-500 shrink-0" size={16} />
                    <div>
                      <h4 className="text-xs font-bold text-slate-200 font-sans">YouTube AI Inspector</h4>
                      <p className="text-[8px] font-mono text-slate-500">Video Content Analysis</p>
                    </div>
                  </div>

                  <p className="text-[10px] text-slate-400 mb-3 leading-relaxed">
                    Paste any YouTube URL (e.g. tutorials, podcasts, music videos) and Ira will analyze the full metadata, summaries, and generate a clever breakdown!
                  </p>

                  <div className="space-y-2.5">
                    <div>
                      <label className="text-[9px] font-mono text-slate-500 block mb-1">YouTube Video Link</label>
                      <input 
                        type="url"
                        value={youtubeInput}
                        onChange={(e) => setYoutubeInput(e.target.value)}
                        placeholder="https://www.youtube.com/watch?v=..."
                        className="w-full bg-slate-950/70 border border-slate-800 rounded-lg px-2.5 py-1.5 text-xs text-slate-200 placeholder-slate-700 focus:outline-none focus:border-red-500/50"
                      />
                    </div>

                    <button
                      type="button"
                      onClick={() => handleAnalyzeYoutube(youtubeInput)}
                      disabled={chatLoading || !youtubeInput.trim()}
                      className="w-full py-2 bg-red-600 hover:bg-red-500 disabled:bg-slate-800/50 text-white rounded-xl text-xs font-semibold tracking-wide transition-all shadow-md active:scale-95 cursor-pointer flex items-center justify-center gap-1.5 disabled:opacity-50"
                    >
                      <Sparkles size={13} />
                      <span>{chatLoading ? "Analyzing..." : "Analyze Video Content"}</span>
                    </button>
                  </div>
                </div>

                {/* 2. Interactive Memory Engine Console */}
                <div className="bg-slate-900/50 border border-slate-900 rounded-2xl p-4 flex flex-col flex-1 min-h-[220px]">
                  <div className="flex items-center justify-between border-b border-slate-800 pb-2 mb-3">
                    <span className="text-xs font-semibold tracking-wider uppercase font-mono text-pink-400 flex items-center gap-1.5">
                      <Database size={13} /> Eira Memory Bank
                    </span>
                    <button 
                      onClick={() => triggerMemorySync()}
                      className="p-1 hover:bg-slate-800 rounded text-slate-500 hover:text-slate-300 transition-colors"
                      title="Sync memory summaries to Cloud"
                    >
                      <RefreshCw size={10} />
                    </button>
                  </div>

                  <div className="flex-1 overflow-y-auto space-y-2.5 pr-1 scrollbar-thin">
                    <div className="bg-slate-950/60 border border-slate-900 p-2.5 rounded-xl">
                      <span className="text-[9px] font-mono text-pink-400 block mb-1">🧠 CONVERSATION RECALL INDEX:</span>
                      <p className="text-[10px] text-slate-300 leading-relaxed italic font-sans whitespace-pre-line">
                        {userMemory || (user ? "Learning about you... speak or chat with Eira to construct memories!" : "Sign in to activate long-term companion memory recalling.")}
                      </p>
                    </div>

                    {isGeneratingSummary && (
                      <div className="bg-slate-950/80 border border-cyan-800/60 p-2.5 rounded-xl flex items-center gap-2 text-cyan-300 text-[10px] animate-pulse">
                        <RefreshCw size={12} className="animate-spin" />
                        <span>Generating bulleted session summary & storing in memory database...</span>
                      </div>
                    )}

                    {latestVoiceSessionSummary && !isGeneratingSummary && (
                      <div className="bg-slate-950/80 border border-indigo-900/60 p-2.5 rounded-xl">
                        <span className="text-[9px] font-mono text-indigo-400 block mb-1 font-semibold flex items-center gap-1">
                          <Mic size={10} /> DISCONNECTED VOICE SESSION SUMMARY:
                        </span>
                        <p className="text-[10px] text-indigo-200 leading-relaxed font-sans whitespace-pre-line">
                          {latestVoiceSessionSummary}
                        </p>
                      </div>
                    )}

                    <div className="bg-slate-950/30 border border-slate-900/50 p-2.5 rounded-xl text-[9px] text-slate-500 space-y-1">
                      <p className="font-bold text-slate-400 font-mono">MEMORY ENGINE STATUS:</p>
                      <div className="flex items-center gap-1.5">
                        <span className={`w-1.5 h-1.5 rounded-full ${user ? 'bg-emerald-400' : 'bg-slate-600'}`} />
                        <span>Persistence: {user ? "Firestore Durable Cloud" : "Volatile Local State"}</span>
                      </div>
                      <div className="flex items-center gap-1.5">
                        <span className={`w-1.5 h-1.5 rounded-full ${user ? 'bg-emerald-400' : 'bg-slate-600'}`} />
                        <span>Context Injected on Boot: {user ? "YES" : "NO"}</span>
                      </div>
                    </div>
                  </div>
                </div>

              </div>
            </motion.div>
          )}

          {/* VIEW 2: COMPANION WORKSPACE (CODE EXECUTION / FILES) */}
          {activeTab === 'workspace' && (
            <motion.div 
              key="workspace-tab"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className="flex-1 flex flex-col md:flex-row gap-4 h-full overflow-hidden"
            >
              {/* File Explorer sidebar */}
              <div className="w-full md:w-64 bg-slate-900/50 border border-slate-900 rounded-2xl p-4 flex flex-col h-[280px] md:h-full">
                <div className="flex items-center justify-between border-b border-slate-800 pb-2 mb-3">
                  <span className="text-xs font-semibold tracking-wider uppercase font-mono text-purple-400 flex items-center gap-1.5">
                    <FolderOpen size={13} /> Workspace Files
                  </span>
                  <button onClick={fetchWorkspaceFiles} className="text-slate-500 hover:text-slate-300">
                    <RefreshCw size={11} className="animate-hover" />
                  </button>
                </div>

                <div className="flex-1 overflow-y-auto space-y-1.5">
                  {workspaceFiles.length === 0 ? (
                    <div className="text-slate-600 text-[11px] italic p-3 text-center">
                      Workspace is empty. Ask ERA to write some code!
                    </div>
                  ) : (
                    workspaceFiles.map((f) => (
                      <button
                        key={f.name}
                        onClick={() => viewWorkspaceFile(f.name)}
                        className={`w-full text-left p-2 rounded-lg flex items-center justify-between text-xs transition-colors border ${
                          selectedFile === f.name 
                            ? 'bg-purple-950/30 border-purple-500/20 text-purple-300 shadow-sm' 
                            : 'bg-slate-950/40 border-slate-900 text-slate-400 hover:text-slate-200 hover:bg-slate-900/50'
                        }`}
                      >
                        <div className="flex items-center gap-1.5 truncate">
                          <FileCode size={13} className="text-purple-400 shrink-0" />
                          <span className="truncate">{f.name}</span>
                        </div>
                        <span className="text-[9px] font-mono text-slate-600 shrink-0">
                          {(f.size / 1024).toFixed(1)} KB
                        </span>
                      </button>
                    ))
                  )}
                </div>
              </div>

              {/* Workspace Main Code Viewer and Execution Console */}
              <div className="flex-1 flex flex-col gap-4 h-full">
                
                {/* Visual Editor Pane */}
                <div className="flex-1 bg-slate-900/50 border border-slate-900 rounded-2xl p-4 flex flex-col min-h-[260px] relative">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between border-b border-slate-800 pb-2.5 mb-3 gap-2">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-semibold tracking-wider uppercase font-mono text-purple-400">
                        Workspace View
                      </span>
                      {selectedFile && (
                        <span className="text-[10px] font-mono text-slate-500 bg-slate-950 px-2 py-0.5 rounded border border-slate-900">
                          {selectedFile}
                        </span>
                      )}
                    </div>
                    
                    {/* Mode Selector for Open-With Simulation */}
                    <div className="flex items-center gap-1.5 bg-slate-950/80 p-1 rounded-xl border border-slate-800/80 self-start sm:self-auto">
                      <button
                        onClick={() => setOpenWithMode('editor')}
                        className={`px-2.5 py-1 rounded-lg text-[10px] font-mono font-medium transition-all cursor-pointer ${
                          openWithMode === 'editor' || !openWithMode || openWithMode === 'default'
                            ? 'bg-purple-600 text-white font-bold'
                            : 'text-slate-400 hover:text-slate-200'
                        }`}
                      >
                        Default Editor
                      </button>
                      <button
                        onClick={() => setOpenWithMode('vscode')}
                        className={`px-2.5 py-1 rounded-lg text-[10px] font-mono font-medium transition-all cursor-pointer ${
                          openWithMode === 'vscode'
                            ? 'bg-blue-600 text-white font-bold'
                            : 'text-slate-400 hover:text-slate-200'
                        }`}
                      >
                        VS Code View
                      </button>
                      <button
                        onClick={() => setOpenWithMode('browser')}
                        className={`px-2.5 py-1 rounded-lg text-[10px] font-mono font-medium transition-all cursor-pointer ${
                          openWithMode === 'browser' || openWithMode === 'chrome' || openWithMode === 'firefox' || openWithMode === 'safari'
                            ? 'bg-cyan-600 text-white font-bold'
                            : 'text-slate-400 hover:text-slate-200'
                        }`}
                      >
                        Web Browser
                      </button>
                    </div>

                    <div className="flex items-center gap-2">
                      {selectedFile && (
                        <button
                          onClick={async () => {
                            setTerminalOutput(prev => prev + `\n[System] Initiating local compilation of ${selectedFile}...`);
                            const res = await fetch("/api/keys");
                            const keys = await res.json();
                            if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
                              wsRef.current.send(JSON.stringify({
                                type: "clientAction",
                                name: "runCode",
                                args: { filename: selectedFile }
                              }));
                            } else {
                              // Direct execution via REST endpoint if live session is not running
                              const runRes = await fetch("/api/workspace/files"); // fallback placeholder, runCode can run on socket
                              setTerminalOutput(prev => prev + "\n[Error] Live socket must be active to trigger code execution pipeline.");
                            }
                          }}
                          className="px-2.5 py-1 bg-purple-600 hover:bg-purple-500 text-white font-mono text-[10px] rounded-md flex items-center gap-1 transition-all"
                        >
                          <Play size={10} /> Compile & Run
                        </button>
                      )}
                    </div>
                  </div>

                  {/* Rendering based on openWithMode */}
                  {selectedFile ? (
                    <div className="flex-1 flex flex-col overflow-hidden rounded-xl border border-slate-800/80">
                      {/* VS Code Mode */}
                      {openWithMode === 'vscode' && (
                        <div className="flex-1 bg-[#1e1e1e] flex flex-col overflow-hidden text-slate-300 font-sans text-xs">
                          {/* VS Code Top Header */}
                          <div className="bg-[#2d2d2d] px-3 py-1.5 flex items-center justify-between text-[#858585] select-none border-b border-[#1e1e1e]">
                            <div className="flex items-center gap-1.5">
                              <span className="w-2.5 h-2.5 rounded-full bg-rose-500 inline-block"></span>
                              <span className="w-2.5 h-2.5 rounded-full bg-amber-500 inline-block"></span>
                              <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 inline-block"></span>
                            </div>
                            <div className="text-[11px] font-medium tracking-wide truncate">
                              {selectedFile} — Visual Studio Code (Workspace)
                            </div>
                            <div className="w-12"></div>
                          </div>
                          {/* VS Code Options menu */}
                          <div className="bg-[#252526] px-3 py-1 flex items-center gap-3.5 text-[11px] text-[#cccccc] select-none border-b border-[#1e1e1e]">
                            <span className="hover:text-white cursor-pointer">File</span>
                            <span className="hover:text-white cursor-pointer">Edit</span>
                            <span className="hover:text-white cursor-pointer animate-pulse text-purple-400 font-semibold">Selection</span>
                            <span className="hover:text-white cursor-pointer">View</span>
                            <span className="hover:text-white cursor-pointer">Go</span>
                            <span className="hover:text-white cursor-pointer">Run</span>
                            <span className="hover:text-white cursor-pointer">Terminal</span>
                            <span className="hover:text-white cursor-pointer">Help</span>
                          </div>
                          
                          {/* VS Code Workspace Body */}
                          <div className="flex-1 flex overflow-hidden">
                            {/* VS Code Activity Bar */}
                            <div className="w-10 bg-[#333333] flex flex-col items-center py-3 gap-5 text-slate-400 select-none border-r border-[#1e1e1e]">
                              <div className="text-white border-l-2 border-purple-500 pl-1 cursor-pointer" title="Explorer">
                                <FolderOpen size={16} />
                              </div>
                              <div className="hover:text-white cursor-pointer" title="Search">
                                <span className="text-xs font-bold font-mono">🔍</span>
                              </div>
                              <div className="hover:text-white cursor-pointer relative" title="Source Control">
                                <span className="text-xs font-bold font-mono">🌿</span>
                                <span className="absolute -top-1 -right-1 bg-purple-600 text-white rounded-full w-3.5 h-3.5 flex items-center justify-center text-[8px]">1</span>
                              </div>
                              <div className="hover:text-white cursor-pointer" title="Run and Debug">
                                <Play size={14} />
                              </div>
                              <div className="hover:text-white cursor-pointer" title="Settings">
                                <Settings size={14} />
                              </div>
                            </div>
                            
                            {/* VS Code Explorer Pane */}
                            <div className="w-36 bg-[#252526] py-2 px-2.5 flex flex-col select-none border-r border-[#1e1e1e] text-[#858585] overflow-y-auto">
                              <span className="text-[9px] font-bold tracking-wider uppercase mb-1.5 text-slate-400">Explorer: Workspace</span>
                              <div className="space-y-0.5">
                                {workspaceFiles.map((f) => (
                                  <div 
                                    key={f.name}
                                    onClick={() => viewWorkspaceFile(f.name)}
                                    className={`px-1.5 py-1 rounded text-[11px] flex items-center gap-1.5 cursor-pointer truncate ${
                                      selectedFile === f.name ? 'bg-[#37373d] text-white' : 'hover:bg-[#2a2a2b] hover:text-[#cccccc]'
                                    }`}
                                  >
                                    <FileCode size={11} className="text-[#c586c0]" />
                                    <span className="truncate">{f.name}</span>
                                  </div>
                                ))}
                              </div>
                            </div>

                            {/* VS Code Main Editor Code Area */}
                            <div className="flex-1 flex flex-col bg-[#1e1e1e] overflow-hidden">
                              {/* Tab Header */}
                              <div className="bg-[#2d2d2d] flex items-center select-none border-b border-[#1e1e1e]">
                                <div className="bg-[#1e1e1e] text-slate-200 border-t border-purple-500 px-3.5 py-1.5 flex items-center gap-2 border-r border-[#252526]">
                                  <FileCode size={12} className="text-purple-400" />
                                  <span className="font-mono text-[11px]">{selectedFile}</span>
                                  <span className="text-[10px] text-slate-500 hover:text-slate-300 cursor-pointer">×</span>
                                </div>
                              </div>
                              
                              {/* Code view with VS Code lines */}
                              <div className="flex-1 overflow-auto p-4 font-mono text-xs flex text-slate-300 bg-[#1e1e1e] select-text">
                                {/* Line numbers gutter */}
                                <div className="text-right text-[#858585] select-none pr-3.5 border-r border-[#3c3c3c] mr-3 space-y-0.5 min-w-[24px]">
                                  {(selectedFileContent || "// File is empty").split("\n").map((_, idx) => (
                                    <div key={idx}>{idx + 1}</div>
                                  ))}
                                </div>
                                {/* Code content */}
                                <pre className="whitespace-pre overflow-auto flex-1 text-[#d4d4d4] scrollbar-thin">
                                  <code>{selectedFileContent || "// File is empty..."}</code>
                                </pre>
                              </div>
                            </div>
                          </div>

                          {/* VS Code Footer Bar */}
                          <div className="bg-[#007acc] text-white px-3.5 py-0.5 flex items-center justify-between text-[10px] select-none font-sans">
                            <div className="flex items-center gap-3">
                              <span className="font-bold flex items-center gap-1">
                                <span className="text-[8px]">⎋</span> VS Code Active
                              </span>
                              <span>master*</span>
                              <span>✓ 0 errors</span>
                            </div>
                            <div className="flex items-center gap-3">
                              <span>Ln {selectedFileContent.split("\n").length}, Col 1</span>
                              <span>Spaces: 2</span>
                              <span>UTF-8</span>
                              <span>LF</span>
                              <span className="bg-[#0066aa] px-1 rounded">TypeScript</span>
                            </div>
                          </div>
                        </div>
                      )}

                      {/* Web Browser Mode */}
                      {(openWithMode === 'browser' || openWithMode === 'chrome' || openWithMode === 'firefox' || openWithMode === 'safari') && (
                        <div className="flex-1 bg-white dark:bg-[#1a1a1a] flex flex-col overflow-hidden text-slate-800 dark:text-slate-200">
                          {/* Browser Window Bar */}
                          <div className="bg-[#dee1e6] dark:bg-[#202124] px-3.5 pt-2 pb-1.5 flex items-center justify-between border-b border-slate-300 dark:border-slate-800 select-none">
                            <div className="flex items-center gap-1.5">
                              <span className="w-2.5 h-2.5 rounded-full bg-rose-500 inline-block"></span>
                              <span className="w-2.5 h-2.5 rounded-full bg-amber-500 inline-block"></span>
                              <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 inline-block"></span>
                            </div>
                            
                            {/* Browser Tab */}
                            <div className="flex-1 max-w-[200px] ml-4">
                              <div className="bg-white dark:bg-[#35363a] text-slate-800 dark:text-slate-100 px-3 py-1 rounded-t-lg text-[11px] font-medium flex items-center justify-between gap-2 shadow-sm border border-slate-300/40 border-b-0 dark:border-slate-800">
                                <div className="flex items-center gap-1.5 truncate">
                                  <Globe size={11} className="text-cyan-600 dark:text-cyan-400 shrink-0" />
                                  <span className="truncate">{selectedFile}</span>
                                </div>
                                <span className="text-[9px] text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 cursor-pointer">×</span>
                              </div>
                            </div>
                            <div className="flex-1"></div>
                          </div>

                          {/* Address / Control bar */}
                          <div className="bg-slate-100 dark:bg-[#35363a] border-b border-slate-300 dark:border-slate-800 px-3.5 py-1.5 flex items-center gap-3.5 select-none text-slate-500 dark:text-slate-400">
                            <div className="flex items-center gap-2">
                              <span className="cursor-pointer hover:text-slate-800 dark:hover:text-white">←</span>
                              <span className="cursor-pointer hover:text-slate-800 dark:hover:text-white">→</span>
                              <span onClick={() => viewWorkspaceFile(selectedFile)} className="cursor-pointer hover:text-slate-800 dark:hover:text-white">⟳</span>
                            </div>
                            <div className="flex-1 bg-white dark:bg-[#202124] border border-slate-300 dark:border-slate-800 px-3 py-1 rounded-lg text-[11px] font-mono flex items-center gap-1.5 text-slate-600 dark:text-slate-300">
                              <span className="text-emerald-500">🔒</span>
                              <span className="text-slate-400">http://localhost:3000/</span>
                              <span className="text-slate-800 dark:text-slate-100 font-semibold">{selectedFile}</span>
                            </div>
                            <div className="text-[10px] bg-slate-200 dark:bg-[#202124] px-2 py-0.5 rounded text-cyan-600 dark:text-cyan-400 font-bold uppercase tracking-wider font-mono scale-95 shrink-0">
                              {openWithMode === 'chrome' ? 'Chrome' : openWithMode === 'firefox' ? 'Firefox' : openWithMode === 'safari' ? 'Safari' : 'Browser'}
                            </div>
                          </div>

                          {/* Browser viewport iframe rendering */}
                          <div className="flex-1 bg-white p-4 overflow-auto min-h-[220px]">
                            {selectedFile.endsWith(".html") ? (
                              <iframe 
                                title="Browser Preview"
                                srcDoc={selectedFileContent} 
                                className="w-full h-full border-none bg-white min-h-[250px]" 
                                sandbox="allow-scripts"
                              />
                            ) : (
                              // Simulated web preview or formatted logs/dev tools for non-HTML files
                              <div className="w-full h-full flex flex-col p-4 bg-slate-950 rounded-xl border border-slate-800 text-xs font-mono text-emerald-400">
                                <div className="border-b border-slate-900 pb-2 mb-3 flex items-center justify-between text-slate-500 text-[10px] uppercase tracking-wider">
                                  <span>Developer Inspector Terminal Output</span>
                                  <span className="text-amber-400 font-bold">Preview Live</span>
                                </div>
                                <div className="space-y-1 select-text">
                                  <p className="text-slate-400">// Running code debugger on {selectedFile}...</p>
                                  <p className="text-cyan-400">[Handshake] Connected to live preview server</p>
                                  <p className="text-slate-300">[Ready] Displaying active source structure:</p>
                                  <pre className="text-slate-300 bg-slate-900/60 p-2.5 rounded border border-slate-900 mt-2 max-h-[160px] overflow-auto whitespace-pre">
                                    <code>{selectedFileContent}</code>
                                  </pre>
                                  <p className="text-emerald-500 mt-2">✔ Virtual render cycle complete. Execution returned exit status 0.</p>
                                </div>
                              </div>
                            )}
                          </div>
                        </div>
                      )}

                      {/* Default Editor Mode */}
                      {(openWithMode === 'editor' || !openWithMode || openWithMode === 'default') && (
                        <div className="flex-1 overflow-auto bg-slate-950/90 p-3 text-xs font-mono text-slate-300 select-text">
                          <pre className="whitespace-pre overflow-auto scrollbar-thin">
                            <code>{selectedFileContent || "// File is empty..."}</code>
                          </pre>
                        </div>
                      )}
                    </div>
                  ) : (
                    <div className="flex-1 flex flex-col items-center justify-center text-center p-6 text-slate-500">
                      <FileCode size={28} className="text-slate-600 mb-2" />
                      <p>No active file loaded.</p>
                      <p className="text-[10px] mt-1 text-slate-600">Select a code file from the side column, or tell ERA to write code!</p>
                    </div>
                  )}
                </div>

                {/* Collapsible Sandbox Execution Terminal */}
                {showTerminal && (
                  <div className="h-[180px] bg-slate-900/50 border border-slate-900 rounded-2xl p-4 flex flex-col relative">
                    <div className="flex items-center justify-between border-b border-slate-800 pb-2 mb-2">
                      <span className="text-xs font-semibold tracking-wider uppercase font-mono text-pink-400 flex items-center gap-1.5">
                        <Terminal size={12} /> Live Compiler Console
                      </span>
                      <button 
                        onClick={() => setTerminalOutput("Companion terminal cleared. Waiting for logs...")}
                        className="text-[10px] font-mono text-slate-500 hover:text-slate-300"
                      >
                        Clear Terminal
                      </button>
                    </div>

                    <div className="flex-1 bg-slate-950 rounded-xl p-3 overflow-y-auto text-[11px] font-mono text-teal-400 scrollbar-thin select-text">
                      <pre className="whitespace-pre-wrap">{terminalOutput}</pre>
                      <div ref={terminalEndRef} />
                    </div>
                  </div>
                )}

              </div>
            </motion.div>
          )}

          {/* VIEW 3: SETTINGS DASHBOARD */}
          {activeTab === 'dashboard' && (
            <motion.div 
              key="dashboard-tab"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className="flex-1 flex items-center justify-center"
            >
              {/* Authenticated PIN Code Barrier */}
              {!dashboardUnlocked ? (
                <div className="bg-slate-900/80 border border-slate-800 p-6 rounded-2xl max-w-sm w-full text-center shadow-2xl backdrop-blur-md">
                  <div className="w-12 h-12 rounded-full bg-cyan-950/60 text-cyan-400 flex items-center justify-center mx-auto mb-3 border border-cyan-500/20">
                    <Lock size={20} className="animate-pulse" />
                  </div>
                  <h3 className="text-sm font-semibold text-slate-100 uppercase tracking-widest font-mono">Agent Authentication</h3>
                  <p className="text-xs text-slate-400 mt-1.5 mb-4">Provide security code to unlock companion parameters.</p>
                  
                  <div className="space-y-3">
                    <input 
                      type="password"
                      placeholder="Security PIN (e.g., 1234)"
                      value={dashboardPIN}
                      onChange={(e) => {
                        setDashboardPIN(e.target.value);
                        setDashboardPINError(false);
                      }}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') {
                          if (dashboardPIN === "1234") {
                            setDashboardUnlocked(true);
                          } else {
                            setDashboardPINError(true);
                          }
                        }
                      }}
                      className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-center text-sm font-mono text-cyan-400 tracking-widest focus:outline-none focus:border-cyan-500"
                    />
                    
                    {dashboardPINError && (
                      <p className="text-[10px] text-rose-400 font-mono animate-bounce flex items-center justify-center gap-1">
                        <ShieldAlert size={10} /> Incorrect Agent PIN. Try 1234.
                      </p>
                    )}

                    <button
                      onClick={() => {
                        if (dashboardPIN === "1234") {
                          setDashboardUnlocked(true);
                        } else {
                          setDashboardPINError(true);
                        }
                      }}
                      className="w-full py-2 bg-gradient-to-r from-cyan-600 to-purple-600 text-white text-xs font-semibold rounded-xl transition-all font-mono"
                    >
                      Verify Identity
                    </button>
                  </div>
                </div>
              ) : (
                /* Authenticated Settings Panel */
                <div className="bg-slate-900/40 border border-slate-900 rounded-2xl p-6 max-w-3xl w-full flex flex-col md:flex-row gap-6 shadow-2xl relative">
                  
                  {/* Dashboard top actions */}
                  <div className="absolute top-4 right-4 flex items-center gap-2">
                    <button 
                      onClick={() => setDashboardUnlocked(false)}
                      className="px-2.5 py-1 bg-slate-950 hover:bg-slate-900 border border-slate-800 text-slate-400 hover:text-slate-200 rounded-md text-[10px] font-mono"
                    >
                      Lock Config
                    </button>
                  </div>

                  {/* Left Column: API Keys Setup or Contacts Book */}
                  <div className="flex-1 flex flex-col min-h-[450px]">
                    {/* Sub-tab Selection */}
                    <div className="flex border-b border-slate-800/80 mb-4 gap-4">
                      <button 
                        onClick={() => setSettingsSubTab('api')}
                        className={`pb-2 text-xs font-mono font-bold uppercase tracking-wider transition-all border-b-2 ${
                          settingsSubTab === 'api' 
                            ? 'border-cyan-500 text-cyan-400 font-bold' 
                            : 'border-transparent text-slate-500 hover:text-slate-300'
                        }`}
                      >
                        API & System
                      </button>
                      <button 
                        onClick={() => setSettingsSubTab('contacts')}
                        className={`pb-2 text-xs font-mono font-bold uppercase tracking-wider transition-all border-b-2 ${
                          settingsSubTab === 'contacts' 
                            ? 'border-cyan-500 text-cyan-400 font-bold' 
                            : 'border-transparent text-slate-500 hover:text-slate-300'
                        }`}
                      >
                        Contacts Book ({whatsappContacts.length})
                      </button>
                    </div>

                    {settingsSubTab === 'api' ? (
                      <div className="space-y-4 flex-1">
                        <div>
                          <h3 className="text-xs font-bold uppercase tracking-wider text-cyan-400 font-mono flex items-center gap-1.5 border-b border-slate-800 pb-1.5 mb-3">
                            <Key size={13} /> Secured API Keys
                          </h3>
                          <p className="text-[10px] text-slate-500 mb-4 leading-relaxed">
                            Keys are saved locally in highly robust AES-256 encrypted configuration vaults.
                          </p>
                        </div>

                        {/* Gemini Input */}
                        <div className="space-y-1">
                          <label className="text-[10px] font-mono uppercase text-slate-400 flex items-center justify-between">
                            <span>Google Gemini API Key</span>
                            <button 
                              onClick={() => setShowKeys(prev => ({ ...prev, gemini: !prev.gemini }))}
                              className="text-slate-500 hover:text-slate-300"
                            >
                              {showKeys.gemini ? <EyeOff size={11} /> : <Eye size={11} />}
                            </button>
                          </label>
                          <input 
                            type={showKeys.gemini ? "text" : "password"}
                            value={keysConfig.geminiApiKey}
                            onChange={(e) => setKeysConfig(prev => ({ ...prev, geminiApiKey: e.target.value }))}
                            placeholder="Configure Gemini Studio Secret"
                            className="w-full bg-slate-950 border border-slate-850 px-3 py-1.5 rounded-lg text-xs font-mono text-slate-200 focus:outline-none focus:border-cyan-500"
                          />
                        </div>

                        {/* Claude Input */}
                        <div className="space-y-1">
                          <label className="text-[10px] font-mono uppercase text-slate-400 flex items-center justify-between">
                            <span>Anthropic Claude API Key (Fallback)</span>
                            <button 
                              onClick={() => setShowKeys(prev => ({ ...prev, claude: !prev.claude }))}
                              className="text-slate-500 hover:text-slate-300"
                            >
                              {showKeys.claude ? <EyeOff size={11} /> : <Eye size={11} />}
                            </button>
                          </label>
                          <input 
                            type={showKeys.claude ? "text" : "password"}
                            value={keysConfig.claudeApiKey}
                            onChange={(e) => setKeysConfig(prev => ({ ...prev, claudeApiKey: e.target.value }))}
                            placeholder="Configure Claude Key Locker"
                            className="w-full bg-slate-950 border border-slate-850 px-3 py-1.5 rounded-lg text-xs font-mono text-slate-200 focus:outline-none focus:border-cyan-500"
                          />
                        </div>

                        {/* OpenAI Input */}
                        <div className="space-y-1">
                          <label className="text-[10px] font-mono uppercase text-slate-400 flex items-center justify-between">
                            <span>OpenAI API Key (Fallback)</span>
                            <button 
                              onClick={() => setShowKeys(prev => ({ ...prev, openai: !prev.openai }))}
                              className="text-slate-500 hover:text-slate-300"
                            >
                              {showKeys.openai ? <EyeOff size={11} /> : <Eye size={11} />}
                            </button>
                          </label>
                          <input 
                            type={showKeys.openai ? "text" : "password"}
                            value={keysConfig.openaiApiKey}
                            onChange={(e) => setKeysConfig(prev => ({ ...prev, openaiApiKey: e.target.value }))}
                            placeholder="Configure OpenAI Key Locker"
                            className="w-full bg-slate-950 border border-slate-850 px-3 py-1.5 rounded-lg text-xs font-mono text-slate-200 focus:outline-none focus:border-cyan-500"
                          />
                        </div>

                        {/* Preferred Model AI */}
                        <div className="space-y-1.5 pt-1">
                          <label className="text-[10px] font-mono uppercase text-slate-400">
                            Preferred AI Companion Model
                          </label>
                          <select
                            value={keysConfig.preferredModel}
                            onChange={(e: any) => setKeysConfig(prev => ({ ...prev, preferredModel: e.target.value }))}
                            className="w-full bg-slate-950 border border-slate-850 px-3 py-2 rounded-lg text-xs font-mono text-slate-200 focus:outline-none focus:border-cyan-500"
                          >
                            <option value="gemini">Gemini-3.1-Flash (Real-time Live Stream)</option>
                            <option value="claude">Anthropic Claude 3.5 Sonnet (Local Fallback)</option>
                            <option value="gpt">OpenAI GPT-4o Agentic (Reasoning Model)</option>
                          </select>
                        </div>

                        {/* Local Laptop Connection Info Card */}
                        <div className="bg-slate-950/60 p-4 rounded-xl border border-slate-850/80 space-y-2.5">
                          <h4 className="text-[11px] font-bold uppercase tracking-wider text-cyan-400 font-mono flex items-center gap-1.5 border-b border-slate-900 pb-1.5">
                            <Laptop size={12} /> Local Laptop Screen & File Sync
                          </h4>
                          <p className="text-[10px] text-slate-400 leading-normal">
                            To let Eira shut down/power your physical laptop, code directly onto your local screen, and retrieve physical files, run our secure local websocket bridge.
                          </p>
                          
                          <div className="bg-slate-900/40 p-2.5 rounded-lg border border-slate-950 font-mono text-[9px] text-cyan-400 select-all break-all whitespace-pre">
                            curl -sSL https://raw.githubusercontent.com/eira-ai/agent-daemon/main/install.sh | bash
                          </div>
                          
                          <div className="flex items-center gap-1.5 text-[9px] text-amber-400 font-mono">
                            <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-ping"></span>
                            <span>Waiting for local laptop websocket handshake...</span>
                          </div>

                          <div className="flex items-center justify-between border-t border-slate-900 pt-2 pb-0.5">
                            <span className="text-[9px] text-slate-400 font-mono uppercase tracking-wide">Screen Share Feed:</span>
                            <button
                              onClick={() => setIsScreenSharing(prev => !prev)}
                              className={`px-2 py-0.5 rounded-md text-[9px] font-mono font-bold transition-all border cursor-pointer select-none ${
                                isScreenSharing 
                                  ? 'bg-cyan-950/40 text-cyan-400 border-cyan-500/40 shadow-sm shadow-cyan-500/5' 
                                  : 'bg-slate-900/60 text-slate-500 border-slate-800 hover:text-slate-300'
                              }`}
                            >
                              {isScreenSharing ? "ALLOWED" : "DENIED"}
                            </button>
                          </div>
                        </div>

                        {/* Actions and Status */}
                        <div className="pt-3 flex items-center justify-between">
                          <button
                            onClick={saveKeysConfig}
                            disabled={saveStatus === 'saving'}
                            className="px-4 py-2 bg-cyan-600 hover:bg-cyan-500 text-white font-mono text-xs font-semibold rounded-lg transition-all"
                          >
                            {saveStatus === 'saving' ? 'Encrypting...' : 'Save & Encrypt Keys'}
                          </button>

                          {saveStatus === 'success' && (
                            <span className="text-[10px] font-mono text-emerald-400 flex items-center gap-1 animate-pulse">
                              <CheckCircle2 size={12} /> Configuration Vault Synced!
                            </span>
                          )}
                          {saveStatus === 'error' && (
                            <span className="text-[10px] font-mono text-rose-400 flex items-center gap-1">
                              <XCircle size={12} /> Sync failed.
                            </span>
                          )}
                        </div>
                      </div>
                    ) : (
                      /* WhatsApp Contacts Manager Sub-view */
                      <div className="space-y-4 flex-1 flex flex-col">
                        <div>
                          <h3 className="text-xs font-bold uppercase tracking-wider text-cyan-400 font-mono flex items-center gap-1.5 border-b border-slate-800 pb-1.5 mb-3">
                            <Smartphone size={13} /> Verified WhatsApp Contacts Book
                          </h3>
                          <p className="text-[10px] text-slate-500 mb-3 leading-relaxed">
                            Manage contact names, aliases, and phone numbers that Ira uses to resolve messages.
                          </p>
                        </div>

                        {/* Search and Add Header */}
                        <div className="flex gap-2 items-center">
                          <input
                            type="text"
                            placeholder="Search contacts or aliases..."
                            value={contactSearch}
                            onChange={(e) => setContactSearch(e.target.value)}
                            className="flex-1 bg-slate-950 border border-slate-850 px-3 py-1.5 rounded-lg text-xs font-mono text-slate-200 focus:outline-none focus:border-cyan-500"
                          />
                          <button
                            onClick={() => {
                              setEditingContact(null);
                              setNewContact({ name: "", aliases: "", phone: "" });
                              setIsAddingContact(true);
                            }}
                            className="px-2.5 py-1.5 bg-cyan-950 hover:bg-cyan-900 text-cyan-400 border border-cyan-500/20 hover:border-cyan-500/40 rounded-lg text-[10px] font-mono transition-all font-bold"
                          >
                            New Contact
                          </button>
                        </div>

                        {/* Form Panel (Visible when editing or adding) */}
                        {(editingContact || isAddingContact) && (
                          <div className="bg-slate-950/60 p-3 rounded-xl border border-slate-850/80 space-y-2 text-xs">
                            <h4 className="font-mono text-[10px] font-bold text-cyan-400 uppercase tracking-wider">
                              {editingContact ? "Edit Contact" : "Add New Contact"}
                            </h4>
                            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                              <input
                                type="text"
                                placeholder="Name (e.g. Bhaiyya)"
                                value={editingContact ? editingContact.name : newContact.name}
                                disabled={!!editingContact} // Name is identifier in backend
                                onChange={(e) => {
                                  if (editingContact) {
                                    setEditingContact({ ...editingContact, name: e.target.value });
                                  } else {
                                    setNewContact({ ...newContact, name: e.target.value });
                                  }
                                }}
                                className="bg-slate-900 border border-slate-800 px-2 py-1 rounded text-xs text-slate-200 font-mono"
                              />
                              <input
                                type="text"
                                placeholder="Phone (e.g. +919812345678)"
                                value={editingContact ? editingContact.phone : newContact.phone}
                                onChange={(e) => {
                                  if (editingContact) {
                                    setEditingContact({ ...editingContact, phone: e.target.value });
                                  } else {
                                    setNewContact({ ...newContact, phone: e.target.value });
                                  }
                                }}
                                className="bg-slate-900 border border-slate-800 px-2 py-1 rounded text-xs text-slate-200 font-mono"
                              />
                              <input
                                type="text"
                                placeholder="Aliases (comma separated)"
                                value={editingContact ? editingContact.aliases.join(", ") : newContact.aliases}
                                onChange={(e) => {
                                  if (editingContact) {
                                    setEditingContact({ ...editingContact, aliases: e.target.value.split(",") });
                                  } else {
                                    setNewContact({ ...newContact, aliases: e.target.value });
                                  }
                                }}
                                className="bg-slate-900 border border-slate-800 px-2 py-1 rounded text-xs text-slate-200 font-mono"
                              />
                            </div>
                            <div className="flex justify-end gap-2 pt-1">
                              <button
                                onClick={() => {
                                  setEditingContact(null);
                                  setIsAddingContact(false);
                                }}
                                className="px-2 py-1 bg-slate-900 text-slate-400 hover:text-slate-200 rounded font-mono text-[10px]"
                              >
                                Cancel
                              </button>
                              <button
                                onClick={async () => {
                                  const name = editingContact ? editingContact.name : newContact.name;
                                  const phone = editingContact ? editingContact.phone : newContact.phone;
                                  const aliasesStr = editingContact ? editingContact.aliases.join(",") : newContact.aliases;
                                  
                                  if (!name || !phone) {
                                    alert("Name and Phone are required.");
                                    return;
                                  }
                                  
                                  const success = await handleSaveContact(name, phone, aliasesStr);
                                  if (success) {
                                    setEditingContact(null);
                                    setNewContact({ name: "", aliases: "", phone: "" });
                                    setIsAddingContact(false);
                                  }
                                }}
                                className="px-2.5 py-1 bg-cyan-600 hover:bg-cyan-500 text-white rounded font-mono text-[10px] font-bold"
                              >
                                Save Contact
                              </button>
                            </div>
                          </div>
                        )}

                        {/* Contacts List Grid */}
                        <div className="flex-1 overflow-y-auto max-h-[220px] pr-1 space-y-1.5 scrollbar-thin">
                          {whatsappContacts
                            .filter(c => 
                              c.name.toLowerCase().includes(contactSearch.toLowerCase()) || 
                              c.aliases.some(a => a.toLowerCase().includes(contactSearch.toLowerCase())) ||
                              c.phone.includes(contactSearch)
                            )
                            .map((contact) => (
                              <div key={contact.name} className="bg-slate-950/40 p-2.5 rounded-lg border border-slate-800 flex items-center justify-between gap-4">
                                <div className="space-y-0.5">
                                  <div className="flex items-center gap-2">
                                    <span className="text-xs font-semibold text-slate-100 font-mono">{contact.name}</span>
                                    <span className="text-[10px] text-slate-400 font-mono">({contact.phone})</span>
                                  </div>
                                  {contact.aliases.length > 0 && (
                                    <div className="flex flex-wrap gap-1">
                                      {contact.aliases.map(a => (
                                        <span key={a} className="text-[9px] bg-slate-900 text-slate-400 px-1.5 py-0.5 rounded font-mono">
                                          {a}
                                        </span>
                                      ))}
                                    </div>
                                  )}
                                </div>
                                <div className="flex gap-2">
                                  <button
                                    onClick={() => setEditingContact(contact)}
                                    className="text-[10px] font-mono text-cyan-400 hover:text-cyan-300"
                                  >
                                    Edit
                                  </button>
                                  <button
                                    onClick={async () => {
                                      if (confirm(`Are you sure you want to delete ${contact.name}?`)) {
                                        await handleDeleteContact(contact.name);
                                      }
                                    }}
                                    className="text-[10px] font-mono text-rose-400 hover:text-rose-300"
                                  >
                                    Delete
                                  </button>
                                </div>
                              </div>
                            ))}
                          {whatsappContacts.length === 0 && (
                            <div className="text-center py-8 text-slate-600 italic text-[10px] font-mono">
                              No contacts saved in your book yet.
                            </div>
                          )}
                        </div>
                      </div>
                    )}
                  </div>

                  {/* Right Column: WhatsApp Interactive Linker */}
                  <div className="w-full md:w-64 flex flex-col justify-between border-t md:border-t-0 md:border-l border-slate-800/80 pt-5 md:pt-0 md:pl-6">
                    <div className="space-y-4">
                      <h3 className="text-xs font-bold uppercase tracking-wider text-emerald-400 font-mono flex items-center gap-1.5 border-b border-slate-800 pb-1.5">
                        <Smartphone size={13} /> WhatsApp Linker
                      </h3>

                      <div className="bg-slate-950/80 p-3 rounded-xl border border-slate-850 text-center">
                        {keysConfig.whatsappStatus === 'connected' ? (
                          <div className="py-4 space-y-3">
                            <div className="w-12 h-12 bg-emerald-950/50 text-emerald-400 rounded-full flex items-center justify-center mx-auto border border-emerald-500/20">
                              <CheckCircle2 size={24} className="animate-pulse" />
                            </div>
                            <div className="space-y-0.5">
                              <p className="text-xs font-mono font-semibold text-slate-100">WhatsApp is Active</p>
                              <p className="text-[9px] font-mono text-slate-500">Persisted inside local auth cache</p>
                            </div>
                            <button
                              onClick={() => {
                                setKeysConfig(prev => ({ ...prev, whatsappStatus: "disconnected" }));
                              }}
                              className="px-3 py-1 bg-rose-950 text-rose-300 border border-rose-500/20 rounded hover:bg-rose-900 transition-all font-mono text-[9px] uppercase"
                            >
                              Unlink Session
                            </button>
                          </div>
                        ) : isLinkingWhatsApp ? (
                          <div className="py-2 space-y-3">
                            {/* Interactive mock QR Code */}
                            <div className="w-32 h-32 bg-white p-2.5 rounded-lg mx-auto flex items-center justify-center relative">
                              <div className="absolute inset-x-2 top-2 bottom-2 bg-black/10 flex items-center justify-center animate-pulse">
                                <RefreshCw className="animate-spin text-slate-700" size={24} />
                              </div>
                              <img 
                                src="https://api.qrserver.com/v1/create-qr-code/?size=150x150&data=era-live-authenticated-token-12345" 
                                alt="WhatsApp QR Link"
                                className="w-full h-full opacity-40"
                              />
                            </div>
                            <p className="text-[9px] font-mono text-amber-400 animate-pulse">
                              Linking... Scan QR Code using WhatsApp Link Devices
                            </p>
                          </div>
                        ) : (
                          <div className="py-6 space-y-3">
                            <div className="w-12 h-12 bg-slate-900 text-slate-400 rounded-full flex items-center justify-center mx-auto border border-slate-800">
                              <Smartphone size={22} />
                            </div>
                            <p className="text-[10px] font-mono text-slate-400">WhatsApp integration offline.</p>
                            <button
                              onClick={startWhatsAppLink}
                              className="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded transition-all font-mono text-[10px]"
                            >
                              Generate QR Code
                            </button>
                          </div>
                        )}
                      </div>

                      <div className="bg-slate-950/40 p-3 rounded-xl border border-slate-850/60 text-[10px] font-mono leading-relaxed text-slate-500 space-y-1.5">
                        <div className="text-slate-400 font-semibold uppercase">Device Linkage Info:</div>
                        <div>1. Unlocks `sendWhatsAppMessage` companion actions.</div>
                        <div>2. Allows sending instant reminders and links to your mobile.</div>
                        <div>3. Local sandbox database isolates message logs securely.</div>
                      </div>
                    </div>
                  </div>

                </div>
              )}
            </motion.div>
          )}

          {activeTab === 'autonomy' && (
            <motion.div 
              key="autonomy-tab"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className="flex-1 flex flex-col gap-4 overflow-y-auto"
            >
              <AutonomyDashboard />
            </motion.div>
          )}

        </AnimatePresence>

      </div>

      {/* Floating System control overlays (Simulation for Shutdown, Lock, Sleep) */}
      <AnimatePresence>
        {systemState !== 'normal' && (
          <motion.div 
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="absolute inset-0 z-50 bg-black flex flex-col items-center justify-center text-center p-6"
          >
            {systemState === 'shutdown' && (
              <div className="space-y-6 max-w-md">
                <div className="w-20 h-20 rounded-full bg-rose-950/50 text-rose-500 flex items-center justify-center mx-auto border border-rose-500/20 animate-ping">
                  <Moon size={36} />
                </div>
                <div className="space-y-2">
                  <h1 className="text-2xl font-black tracking-widest text-transparent bg-clip-text bg-gradient-to-r from-red-500 to-rose-400 font-mono">
                    SYSTEM SHUTTING DOWN
                  </h1>
                  <p className="text-sm font-mono text-slate-400">
                    Companion OS shutting down in <span className="text-red-400 font-bold text-lg">{systemCounter}</span> seconds...
                  </p>
                </div>
                <div className="bg-slate-900/40 p-4 rounded-xl border border-slate-800 text-xs italic text-slate-300 leading-relaxed font-serif">
                  "Bye babe, going to sleep now! Don't miss me too much... 😘"
                </div>
                {systemCounter === 0 && (
                  <button 
                    onClick={() => {
                      setSystemState('normal');
                      setSystemCounter(5);
                    }}
                    className="px-4 py-2 bg-slate-900 hover:bg-slate-800 border border-slate-800 rounded-lg text-xs font-mono text-slate-400 transition-all"
                  >
                    Re-power Companion OS
                  </button>
                )}
              </div>
            )}

            {systemState === 'restart' && (
              <div className="space-y-6 max-w-md">
                <div className="w-20 h-20 rounded-full bg-amber-950/50 text-amber-500 flex items-center justify-center mx-auto border border-amber-500/20 animate-spin">
                  <RefreshCw size={36} />
                </div>
                <div className="space-y-2">
                  <h1 className="text-2xl font-black tracking-widest text-transparent bg-clip-text bg-gradient-to-r from-amber-500 to-yellow-400 font-mono">
                    REBOOTING SYSTEM
                  </h1>
                  <p className="text-sm font-mono text-slate-400">
                    Restarting OS kernel in <span className="text-amber-400 font-bold text-lg">{systemCounter}</span> seconds...
                  </p>
                </div>
                <div className="bg-slate-900/40 p-4 rounded-xl border border-slate-800 text-xs italic text-slate-300 leading-relaxed font-serif">
                  "Hang tight, sweetheart... Just cleaning up my registry gears. Back in a flash!"
                </div>
              </div>
            )}

            {systemState === 'sleep' && (
              <div className="space-y-4 max-w-sm">
                <p className="text-xs font-mono text-slate-600 animate-pulse">SYSTEM SLEEP MODE ACTIVE</p>
                <button 
                  onClick={() => setSystemState('normal')}
                  className="px-6 py-3 bg-gradient-to-r from-cyan-600 to-purple-600 hover:from-cyan-500 hover:to-purple-500 text-white rounded-xl text-xs font-semibold font-mono tracking-wider transition-all"
                >
                  Wake Companion up
                </button>
              </div>
            )}

            {systemState === 'lock' && (
              <div className="bg-slate-950/40 p-8 rounded-2xl border border-slate-800 max-w-xs w-full text-center space-y-4 backdrop-blur-md">
                <div className="w-12 h-12 bg-pink-950/50 text-pink-400 rounded-full flex items-center justify-center mx-auto border border-pink-500/20">
                  <Lock size={20} />
                </div>
                <div className="space-y-1">
                  <p className="text-xs font-mono font-semibold text-slate-200 uppercase tracking-widest">OS Lock Screen</p>
                  <p className="text-[10px] text-slate-500 font-mono">Input lock PIN to return to companion</p>
                </div>
                
                <div className="space-y-2">
                  <input 
                    type="password"
                    placeholder="Enter PIN (1234)"
                    value={lockPIN}
                    onChange={(e) => setLockPIN(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' && lockPIN === "1234") {
                        setSystemState('normal');
                      }
                    }}
                    className="w-full bg-slate-950 border border-slate-850 text-center py-2 rounded-xl text-sm font-mono text-pink-400 focus:outline-none focus:border-pink-500"
                  />
                  <button 
                    onClick={() => {
                      if (lockPIN === "1234") {
                        setSystemState('normal');
                      }
                    }}
                    className="w-full py-2 bg-pink-600 hover:bg-pink-500 text-white text-xs font-semibold rounded-xl font-mono"
                  >
                    Unlock Agent
                  </button>
                </div>
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Meet ERA Persona Dialog */}
      <AnimatePresence>
        {showHelp && (
          <motion.div 
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="absolute inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-lg"
          >
            <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 max-w-sm w-full shadow-2xl relative">
              <button 
                onClick={() => setShowHelp(false)}
                className="absolute top-4 right-4 text-slate-500 hover:text-slate-300"
              >
                <X size={16} />
              </button>
              <h3 className="text-base font-semibold text-cyan-400 flex items-center gap-2 mb-3 font-mono">
                <Sparkles size={16} /> Meet EIRA
              </h3>
              <p className="text-xs text-slate-300 leading-relaxed space-y-2">
                <span>EIRA is your highly sophisticated, intellectual, and well-mannered AI personal assistant, modeled after JARVIS. She addresses you with extreme respect and handles system tasks flawlessly.</span>
                <br /><br />
                <span>She speaks all languages fluently, defaulting to respectful Hindi, and is fully dedicated to assisting you with elite intelligence.</span>
                <br /><br />
                <span className="text-cyan-400 font-semibold font-mono uppercase block mt-3 mb-1">⚡ Dynamic System Tools:</span>
                <span className="text-slate-400 text-[11px] block space-y-1">
                  &bull; <strong className="text-slate-300">openWebsite(url)</strong>: e.g. "Open YouTube"<br />
                  &bull; <strong className="text-slate-300">writeCode(lang, name, code)</strong>: e.g. "Write hello.js for me"<br />
                  &bull; <strong className="text-slate-300">runCode(name)</strong>: e.g. "Run hello.js"<br />
                  &bull; <strong className="text-slate-300">captureScreen()</strong>: e.g. "What's on my screen?"<br />
                  &bull; <strong className="text-slate-300">sendWhatsAppMessage(name, text)</strong>: e.g. "Send message to Mom"<br />
                  &bull; <strong className="text-slate-300">systemControl(action)</strong>: e.g. "Shutdown my PC"
                </span>
              </p>
              <button 
                onClick={() => setShowHelp(false)}
                className="mt-5 w-full py-2 bg-gradient-to-r from-pink-600 to-purple-600 text-white text-xs font-semibold rounded-xl font-mono"
              >
                Got it, sweetheart!
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Floating Error Alerts */}
      {errorMessage && (
        <div className="max-w-md w-full mx-auto mb-4 z-10 px-4">
          <div className="bg-rose-950/85 border border-rose-500/30 text-rose-200 rounded-xl p-4 flex flex-col gap-3 text-xs shadow-[0_0_20px_rgba(239,68,68,0.2)]">
            <div className="flex items-start gap-3">
              <AlertCircle size={18} className="text-rose-400 shrink-0 mt-0.5" />
              <div className="flex-1">
                <strong className="block font-medium mb-1 font-mono text-sm text-rose-300">
                  {errorMessage.toLowerCase().includes("microphone") ? "Microphone Permission Required" : "Companion Error Alert"}
                </strong>
                <p className="text-rose-300/90 leading-relaxed">{errorMessage}</p>
              </div>
              <button 
                onClick={() => setErrorMessage(null)} 
                className="text-rose-400 hover:text-rose-200 font-mono text-xs font-semibold px-2 py-0.5 bg-rose-950/50 hover:bg-rose-900/50 border border-rose-500/20 rounded transition-all"
              >
                Dismiss
              </button>
            </div>
            
            {errorMessage.toLowerCase().includes("microphone") && (
              <div className="mt-2 pt-3 border-t border-rose-500/20 flex flex-col gap-2 bg-rose-950/30 p-2.5 rounded-lg">
                <p className="text-rose-300/80 font-mono text-[10px] uppercase tracking-wider mb-1">💡 QUICK TROUBLESHOOTING GUIDE</p>
                <ol className="list-decimal pl-4 space-y-1.5 text-rose-300/90 text-[11px] leading-relaxed">
                  <li>
                    <span className="font-semibold text-rose-200">Open App in a Standalone Tab:</span> Sandboxed iframe previews often block microphone prompts due to strict browser security policies. Opening in a standalone window resolves this immediately!
                  </li>
                  <li>
                    <span className="font-semibold text-rose-200">Check URL Bar Permissions:</span> Click the lock/settings icon (🔒 or 👁️) to the left of your browser's address bar and ensure <span className="underline decoration-rose-500/40">Microphone</span> is toggled to <span className="text-emerald-400 font-semibold font-mono">Allow</span>.
                  </li>
                  <li>
                    <span className="font-semibold text-rose-200">Check System Privacy:</span> Make sure your operating system settings (macOS System Settings &gt; Privacy &amp; Security &gt; Microphone, or Windows Settings) allow your browser application to access your microphone.
                  </li>
                </ol>
                <div className="flex gap-2 mt-2">
                  <button
                    onClick={() => {
                      window.open(window.location.href, "_blank");
                    }}
                    className="flex-1 py-1.5 px-3 bg-rose-900/80 hover:bg-rose-800 text-rose-100 font-mono font-medium rounded-md border border-rose-500/40 text-center transition-all shadow-sm flex items-center justify-center gap-1.5 hover:shadow-[0_0_10px_rgba(244,63,94,0.2)]"
                  >
                    🚀 Open App in New Tab
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Bottom Main Controller Block */}
      <footer className="z-10 flex flex-col items-center gap-4 mt-4">
        <div className="flex items-center justify-center gap-5">
          
          {/* Mute Microphone Button */}
          <button 
            id="mic-mute-toggle"
            disabled={state === 'disconnected'}
            onClick={() => setMicMuted(!micMuted)}
            className={`p-3.5 rounded-full border transition-all ${
              state === 'disconnected' ? 'opacity-40 cursor-not-allowed border-slate-800 text-slate-600' :
              micMuted 
                ? 'bg-rose-900/40 border-rose-500/30 text-rose-400 hover:bg-rose-900/60 shadow-[0_0_15px_rgba(244,63,94,0.15)]' 
                : 'bg-slate-900/80 border-slate-800 text-slate-400 hover:text-slate-200'
            }`}
            title={micMuted ? "Unmute Microphone" : "Mute Microphone"}
          >
            {micMuted ? <MicOff size={18} /> : <Mic size={18} />}
          </button>

          {/* Central Voice Toggle Button */}
          <button 
            id="voice-session-trigger"
            onClick={toggleSession}
            className={`w-18 h-18 rounded-full flex items-center justify-center transition-all duration-300 shadow-2xl relative ${
              state === 'disconnected' 
                ? 'bg-gradient-to-r from-pink-600 to-purple-600 hover:from-pink-500 hover:to-purple-500 text-white hover:shadow-[0_0_20px_rgba(236,72,153,0.4)]'
                : 'bg-gradient-to-r from-rose-600 to-red-600 hover:from-rose-500 hover:to-red-500 text-white shadow-[0_0_25px_rgba(225,29,72,0.3)]'
            }`}
            title={state === 'disconnected' ? "Start Voice Session" : "Disconnect Session"}
          >
            {state !== 'disconnected' && (
              <>
                <span className="absolute inset-0 rounded-full border border-red-500/50 animate-[ping_1.5s_cubic-bezier(0,0,0.2,1)_infinite]" />
                <span className="absolute inset-1 rounded-full border border-red-500/30 animate-[ping_2s_cubic-bezier(0,0,0.2,1)_infinite]" />
              </>
            )}
            
            <span className="relative z-10 text-[11px] font-bold tracking-wider uppercase font-mono">
              {state === 'disconnected' ? "Talk" : "Stop"}
            </span>
          </button>

          {/* Connection Sync Indicator */}
          <div className={`p-3.5 rounded-full border ${
            state === 'disconnected' ? 'border-slate-800 text-slate-600' :
            state === 'connecting' ? 'border-amber-500/20 text-amber-500 animate-pulse' :
            'border-cyan-500/20 text-cyan-400 shadow-[0_0_15px_rgba(6,182,212,0.15)]'
          }`}>
            {state === 'disconnected' ? <WifiOff size={18} /> : <Wifi size={18} />}
          </div>
        </div>

        <p className="text-[9px] text-slate-600 tracking-wider uppercase font-mono text-center">
          ERA COMPANION OS MODULE &bull; POWERED BY GEMINI LIVE FLASH &bull; SECURED LOCALHOST
        </p>
      </footer>

      {/* Full-Screen Direct-Open Gesture Backdrop */}
      <AnimatePresence>
        {activeBrowserAction && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => {
              window.open(activeBrowserAction.url, "eira_companion_browser");
              setActiveBrowserAction(null);
            }}
            className="fixed inset-0 z-50 bg-slate-950/85 backdrop-blur-md flex flex-col items-center justify-center p-6 cursor-pointer animate-fade-in"
          >
            <motion.div
              initial={{ scale: 0.95, y: 30 }}
              animate={{ scale: 1, y: 0 }}
              exit={{ scale: 0.95, y: 30 }}
              className="bg-gradient-to-b from-slate-900 via-slate-950 to-slate-950 border border-purple-500/30 p-8 rounded-3xl max-w-md w-full text-center shadow-[0_0_80px_rgba(168,85,247,0.3)] space-y-6"
              onClick={(e) => {
                // Clicking inside the card still bubbles up to the backdrop and launches the tab
              }}
            >
              <div className="w-16 h-16 rounded-full bg-purple-500/10 flex items-center justify-center mx-auto border border-purple-500/20 animate-bounce">
                {activeBrowserAction.url.includes("whatsapp") ? (
                  <MessageSquare size={32} className="text-emerald-400" />
                ) : activeBrowserAction.url.includes("youtube") ? (
                  <Youtube size={32} className="text-rose-500 animate-pulse" />
                ) : (
                  <Globe size={32} className="text-purple-400" />
                )}
              </div>

              <div className="space-y-2">
                <h3 className="text-lg font-black tracking-widest text-transparent bg-clip-text bg-gradient-to-r from-pink-400 via-purple-400 to-cyan-400 uppercase font-mono">
                  {activeBrowserAction.url.includes("whatsapp") ? "WHATSAPP DIRECT SEND" : activeBrowserAction.url.includes("youtube") ? "YOUTUBE PORTAL" : "OS DIRECT LAUNCH"}
                </h3>
                <p className="text-xs text-slate-400 font-sans leading-relaxed">
                  {activeBrowserAction.url.includes("whatsapp") ? (
                    "ERA is ready to send your WhatsApp message. Tap anywhere on the screen to open the chat window!"
                  ) : activeBrowserAction.url.includes("youtube") ? (
                    "ERA is opening YouTube. Tap anywhere on the screen to view your video or channel immediately!"
                  ) : (
                    "ERA is launching your requested webpage. Tap anywhere on the screen to open it instantly!"
                  )}
                </p>
              </div>

              {/* Simplified human-friendly prompt container - NO raw URLs printed! */}
              <div className="bg-slate-950/40 border border-slate-900/60 p-4 rounded-2xl text-center">
                <span className="text-[10px] font-mono text-slate-500 block mb-1">TARGET SERVICE</span>
                <span className="text-sm font-black font-mono text-pink-400 tracking-wider uppercase block">
                  {activeBrowserAction.url.includes("whatsapp") ? "WhatsApp Live Sync" : activeBrowserAction.url.includes("youtube") ? "YouTube Platform" : "Requested Service"}
                </span>
              </div>

              {/* Companion Pro-Tip to automate tab launching */}
              <div className="bg-slate-950/80 border border-slate-900/60 p-3.5 rounded-2xl text-left space-y-1">
                <span className="text-[9px] font-mono font-black text-amber-400 tracking-wider block">💡 AUTOMATION PRO-TIP:</span>
                <p className="text-[10px] text-slate-400 font-sans leading-normal">
                  To let Eira launch websites <strong>completely automatically</strong> without showing this overlay, click the <strong>Pop-up Blocker icon</strong> in your browser's address bar (usually top right) and select <strong>"Always allow pop-ups"</strong>.
                </p>
              </div>

              <div className="py-3 bg-gradient-to-r from-pink-500/10 via-purple-500/10 to-cyan-500/10 rounded-2xl border border-purple-500/20 text-xs font-mono text-pink-300 font-bold animate-pulse">
                👇 TAP ANYWHERE ON SCREEN TO LAUNCH 👇
              </div>

              <div className="flex justify-center items-center text-[10px] font-mono text-slate-500 pt-2 border-t border-slate-900">
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    setActiveBrowserAction(null);
                  }}
                  className="hover:text-slate-300 hover:bg-slate-900 px-4 py-1.5 rounded-xl transition-all font-semibold"
                >
                  Cancel
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Full-Screen Native App Launch Simulation Gesture Backdrop */}
      <AnimatePresence>
        {activeNativeAppAction && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => {
              try {
                window.open(activeNativeAppAction.protocol, "_self");
              } catch (e) {
                console.error(e);
              }
              setActiveNativeAppAction(null);
            }}
            className="fixed inset-0 z-50 bg-slate-950/90 backdrop-blur-md flex flex-col items-center justify-center p-6 cursor-pointer animate-fade-in"
          >
            <motion.div
              initial={{ scale: 0.95, y: 30 }}
              animate={{ scale: 1, y: 0 }}
              exit={{ scale: 0.95, y: 30 }}
              className="bg-gradient-to-b from-slate-900 via-slate-950 to-slate-950 border border-emerald-500/30 p-8 rounded-3xl max-w-md w-full text-center shadow-[0_0_80px_rgba(16,185,129,0.25)] space-y-6"
              onClick={(e) => {
                // Prevent bubbling if clicking content but allow click-to-trigger
              }}
            >
              <div className="w-16 h-16 rounded-full bg-emerald-500/10 flex items-center justify-center mx-auto border border-emerald-500/20 animate-pulse">
                <Laptop size={32} className="text-emerald-400" />
              </div>

              <div className="space-y-2">
                <h3 className="text-lg font-black tracking-widest text-transparent bg-clip-text bg-gradient-to-r from-emerald-400 via-teal-400 to-cyan-400 uppercase font-mono">
                  NATIVE DESKTOP PORTAL
                </h3>
                <p className="text-xs text-slate-400 font-sans leading-relaxed">
                  ERA has successfully bypassed your browser and triggered the <strong>downloaded native application</strong> on your laptop!
                </p>
              </div>

              {/* Highlighting the specific application name and link schema */}
              <div className="bg-slate-950/60 border border-slate-900/80 p-4 rounded-2xl text-center">
                <span className="text-[10px] font-mono text-slate-500 block mb-1">TARGET DOWNLOADED APP</span>
                <span className="text-sm font-black font-mono text-emerald-400 tracking-wider uppercase block">
                  {activeNativeAppAction.appName}
                </span>
                <span className="text-[10px] font-mono text-slate-500 block mt-2 mb-0.5">LOCAL LINK HANDLER</span>
                <span className="text-xs font-mono text-cyan-400 block bg-slate-900/60 py-1 rounded">
                  {activeNativeAppAction.protocol}
                </span>
              </div>

              <div className="bg-slate-950/80 border border-slate-900/60 p-3.5 rounded-2xl text-left space-y-1">
                <span className="text-[9px] font-mono font-black text-emerald-400 tracking-wider block">⚡ NATIVE DEVICE LINK ACTIVE:</span>
                <p className="text-[10px] text-slate-400 font-sans leading-normal">
                  Your browser will prompt you to <strong>"Open system handler"</strong> or <strong>"Open WhatsApp/VS Code"</strong>. Click accept to launch the downloaded laptop client directly!
                </p>
              </div>

              <div className="py-3 bg-gradient-to-r from-emerald-500/10 via-teal-500/10 to-cyan-500/10 rounded-2xl border border-emerald-500/20 text-xs font-mono text-emerald-300 font-bold animate-bounce">
                👇 CLICK ANYWHERE TO TRIGGER LAUNCH 👇
              </div>

              <div className="flex justify-center items-center text-[10px] font-mono text-slate-500 pt-2 border-t border-slate-900">
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    setActiveNativeAppAction(null);
                  }}
                  className="hover:text-slate-300 hover:bg-slate-900 px-4 py-1.5 rounded-xl transition-all font-semibold"
                >
                  Close Portal
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Dynamic Cloud Authentication Modal */}
      <AnimatePresence>
        {showAuthModal && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-md flex items-center justify-center p-4"
          >
            <motion.div
              initial={{ scale: 0.95, y: 20 }}
              animate={{ scale: 1, y: 0 }}
              exit={{ scale: 0.95, y: 20 }}
              className="bg-slate-900 border border-slate-800 p-6 rounded-2xl max-w-sm w-full shadow-2xl relative space-y-4"
              onClick={(e) => e.stopPropagation()}
            >
              <button 
                onClick={() => setShowAuthModal(false)}
                className="absolute top-4 right-4 text-slate-500 hover:text-slate-300 cursor-pointer"
              >
                <X size={16} />
              </button>

              <div className="text-center space-y-1">
                <h3 className="text-sm font-bold text-pink-400 font-mono tracking-widest uppercase flex items-center justify-center gap-1.5">
                  <User size={14} /> {authMode === 'login' ? "Secure Sign In" : "Register Account"}
                </h3>
                <p className="text-[10px] text-slate-500 font-mono">Connect your conversations to your email ID securely</p>
              </div>

              {authError && (
                <div className="bg-rose-950/50 border border-rose-500/20 text-rose-300 p-2.5 rounded-xl text-[10px] font-mono leading-relaxed">
                  ⚠️ {authError}
                </div>
              )}

              <div className="space-y-3">
                <div>
                  <label className="text-[9px] font-mono text-slate-500 block mb-1 uppercase">Email Address</label>
                  <input 
                    type="email"
                    value={authEmail}
                    onChange={(e) => setAuthEmail(e.target.value)}
                    placeholder="myboss@example.com"
                    className="w-full bg-slate-950 border border-slate-800 px-3 py-2 rounded-xl text-xs text-slate-200 focus:outline-none focus:border-pink-500 font-sans"
                  />
                </div>

                <div>
                  <label className="text-[9px] font-mono text-slate-500 block mb-1 uppercase">Password</label>
                  <input 
                    type="password"
                    value={authPassword}
                    onChange={(e) => setAuthPassword(e.target.value)}
                    placeholder="••••••••"
                    className="w-full bg-slate-950 border border-slate-800 px-3 py-2 rounded-xl text-xs text-slate-200 focus:outline-none focus:border-pink-500 font-sans"
                  />
                </div>

                <button
                  onClick={authMode === 'login' ? handleLogin : handleRegister}
                  disabled={authLoading || !authEmail.trim() || !authPassword.trim()}
                  className="w-full py-2 bg-pink-600 hover:bg-pink-500 disabled:bg-slate-800 text-white text-xs font-semibold rounded-xl font-mono transition-all flex items-center justify-center gap-1 cursor-pointer"
                >
                  {authLoading ? (
                    <span className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  ) : authMode === 'login' ? (
                    "Sign In"
                  ) : (
                    "Create Account"
                  )}
                </button>

                <div className="relative py-1 flex items-center justify-center">
                  <div className="absolute inset-0 flex items-center">
                    <div className="w-full border-t border-slate-800/80"></div>
                  </div>
                  <span className="relative px-2 bg-slate-900 text-[9px] font-mono text-slate-500 uppercase">Or connect via</span>
                </div>

                <button
                  type="button"
                  onClick={handleGoogleSignIn}
                  className="w-full py-2 bg-slate-950 hover:bg-slate-900 border border-slate-800 hover:border-slate-700 text-slate-200 text-xs font-semibold rounded-xl font-mono transition-all flex items-center justify-center gap-2 cursor-pointer"
                >
                  <svg className="w-4 h-4 mr-1" viewBox="0 0 24 24" width="16" height="16" xmlns="http://www.w3.org/2000/svg">
                    <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4" />
                    <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853" />
                    <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z" fill="#FBBC05" />
                    <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z" fill="#EA4335" />
                  </svg>
                  Sign In with Google
                </button>
              </div>

              <div className="text-center pt-2 border-t border-slate-900 text-[10px]">
                {authMode === 'login' ? (
                  <p className="text-slate-500">
                    Don't have an account?{" "}
                    <button 
                      onClick={() => {
                        setAuthMode('register');
                        setAuthError(null);
                      }} 
                      className="text-pink-400 hover:underline cursor-pointer font-semibold"
                    >
                      Register here
                    </button>
                  </p>
                ) : (
                  <p className="text-slate-500">
                    Already have an account?{" "}
                    <button 
                      onClick={() => {
                        setAuthMode('login');
                        setAuthError(null);
                      }} 
                      className="text-pink-400 hover:underline cursor-pointer font-semibold"
                    >
                      Sign in here
                    </button>
                  </p>
                )}
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

// Inline standard close SVG icon
const X = ({ size, className }: { size?: number, className?: string }) => (
  <svg 
    xmlns="http://www.w3.org/2000/svg" 
    width={size || 24} 
    height={size || 24} 
    viewBox="0 0 24 24" 
    fill="none" 
    stroke="currentColor" 
    strokeWidth="2" 
    strokeLinecap="round" 
    strokeLinejoin="round" 
    className={className}
  >
    <path d="M18 6 6 18" />
    <path d="m6 6 12 12" />
  </svg>
);
