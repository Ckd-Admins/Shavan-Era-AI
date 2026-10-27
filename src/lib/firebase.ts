import { initializeApp } from "firebase/app";
import { 
  getAuth, 
  signInWithEmailAndPassword, 
  createUserWithEmailAndPassword, 
  signOut, 
  onAuthStateChanged,
  signInWithPopup,
  GoogleAuthProvider,
  User
} from "firebase/auth";
import { 
  initializeFirestore,
  collection, 
  doc, 
  setDoc, 
  getDoc, 
  addDoc, 
  query, 
  orderBy, 
  limit, 
  getDocs, 
  updateDoc 
} from "firebase/firestore";

// Configuration loaded from firebase-applet-config.json
const firebaseConfig = {
  projectId: "silken-music-nj4jh",
  appId: "1:695189218456:web:1aeeec14effc216dcedced",
  apiKey: "AIzaSyDSUiPjK1V-RKzVOJh4ybm0LCo7m52mf1A",
  authDomain: "silken-music-nj4jh.firebaseapp.com",
  storageBucket: "silken-music-nj4jh.firebasestorage.app",
  messagingSenderId: "695189218456"
};

const databaseId = "ai-studio-eravoiceassistan-e63251dc-9788-42f6-b9e9-3efcf97d3e36";

// Initialize Firebase
const app = initializeApp(firebaseConfig);
const auth = getAuth(app);
// Initialize Firestore using the custom database ID provisioned for this applet and enabling force long polling to bypass websocket issues
const db = initializeFirestore(app, {
  experimentalForceLongPolling: true,
}, databaseId);

export { app, auth, db };

// Interfaces
export interface ChatMessage {
  id: string;
  sender: "user" | "model";
  text: string;
  timestamp: any; // Firestore timestamp or standard Date
  type?: "text" | "youtube_analysis" | "voice";
  youtubeUrl?: string;
  youtubeTitle?: string;
}

export interface UserProfile {
  email: string;
  displayName?: string;
  memorySummary: string;
  lastUpdated: any;
}

export enum OperationType {
  CREATE = 'create',
  UPDATE = 'update',
  DELETE = 'delete',
  LIST = 'list',
  GET = 'get',
  WRITE = 'write',
}

interface FirestoreErrorInfo {
  error: string;
  operationType: OperationType;
  path: string | null;
  authInfo: {
    userId?: string | null;
    email?: string | null;
    emailVerified?: boolean | null;
    isAnonymous?: boolean | null;
    tenantId?: string | null;
    providerInfo?: {
      providerId?: string | null;
      email?: string | null;
    }[];
  }
}

function handleFirestoreError(error: unknown, operationType: OperationType, path: string | null) {
  const errMsg = error instanceof Error ? error.message : String(error);
  const isOfflineOrNetwork = 
    errMsg.includes("offline") || 
    errMsg.includes("Could not reach Cloud Firestore") ||
    errMsg.includes("Backend didn't respond") ||
    errMsg.includes("unavailable") ||
    errMsg.includes("network") ||
    errMsg.includes("deadline-exceeded") ||
    errMsg.includes("failed-precondition") ||
    errMsg.includes("permission-denied");

  const errInfo: FirestoreErrorInfo = {
    error: errMsg,
    authInfo: {
      userId: auth.currentUser?.uid,
      email: auth.currentUser?.email,
      emailVerified: auth.currentUser?.emailVerified,
      isAnonymous: auth.currentUser?.isAnonymous,
      tenantId: auth.currentUser?.tenantId,
      providerInfo: auth.currentUser?.providerData?.map(provider => ({
        providerId: provider.providerId,
        email: provider.email,
      })) || []
    },
    operationType,
    path
  };

  if (isOfflineOrNetwork) {
    console.warn(`[Firestore Offline/Network Warning] Operation '${operationType}' on '${path}' operating in offline mode: ${errMsg}`);
    return;
  }

  console.error('Firestore Error: ', JSON.stringify(errInfo));
  throw new Error(JSON.stringify(errInfo));
}

/**
 * Save a new message to the user's history
 */
export async function saveMessageToHistory(userEmail: string, message: Omit<ChatMessage, "id">) {
  const userPath = `users/${userEmail.toLowerCase()}`;
  try {
    const userRef = doc(db, "users", userEmail.toLowerCase());
    // Ensure user profile document exists
    const userSnap = await getDoc(userRef);
    if (!userSnap.exists()) {
      await setDoc(userRef, {
        email: userEmail.toLowerCase(),
        memorySummary: "User is new. Keep responses warm and inviting.",
        lastUpdated: new Date()
      });
    }

    // Save to subcollection of chats
    const chatsCol = collection(db, "users", userEmail.toLowerCase(), "chats");
    await addDoc(chatsCol, {
      sender: message.sender,
      text: message.text,
      timestamp: new Date(),
      type: message.type || "text",
      youtubeUrl: message.youtubeUrl || null,
      youtubeTitle: message.youtubeTitle || null
    });
  } catch (error) {
    handleFirestoreError(error, OperationType.WRITE, userPath);
  }
}

/**
 * Retrieve the chat history for a user
 */
export async function loadChatHistory(userEmail: string): Promise<ChatMessage[]> {
  const chatsPath = `users/${userEmail.toLowerCase()}/chats`;
  try {
    const chatsCol = collection(db, "users", userEmail.toLowerCase(), "chats");
    const q = query(chatsCol, orderBy("timestamp", "asc"), limit(100));
    const snapshot = await getDocs(q);
    
    return snapshot.docs.map(doc => {
      const data = doc.data();
      return {
        id: doc.id,
        sender: data.sender,
        text: data.text,
        timestamp: data.timestamp?.toDate() || new Date(),
        type: data.type || "text",
        youtubeUrl: data.youtubeUrl || undefined,
        youtubeTitle: data.youtubeTitle || undefined
      };
    });
  } catch (error) {
    handleFirestoreError(error, OperationType.LIST, chatsPath);
    return [];
  }
}

/**
 * Load user profile containing long-term memory
 */
export async function loadUserProfile(userEmail: string): Promise<UserProfile | null> {
  const userPath = `users/${userEmail.toLowerCase()}`;
  try {
    const userRef = doc(db, "users", userEmail.toLowerCase());
    const snap = await getDoc(userRef);
    if (snap.exists()) {
      const data = snap.data();
      return {
        email: data.email,
        displayName: data.displayName,
        memorySummary: data.memorySummary || "",
        lastUpdated: data.lastUpdated?.toDate() || new Date()
      };
    }
    return null;
  } catch (error) {
    handleFirestoreError(error, OperationType.GET, userPath);
    return null;
  }
}

/**
 * Update the user's long-term memory summary in Firestore
 */
export async function updateUserMemorySummary(userEmail: string, memorySummary: string) {
  const userPath = `users/${userEmail.toLowerCase()}`;
  try {
    const userRef = doc(db, "users", userEmail.toLowerCase());
    await setDoc(userRef, {
      memorySummary,
      lastUpdated: new Date()
    }, { merge: true });
  } catch (error) {
    handleFirestoreError(error, OperationType.WRITE, userPath);
  }
}

/**
 * Save a bulleted voice session summary to Firestore
 */
export async function saveVoiceSessionSummary(userEmail: string, sessionSummary: string, transcriptCount: number) {
  const userPath = `users/${userEmail.toLowerCase()}/voice_sessions`;
  try {
    const colRef = collection(db, "users", userEmail.toLowerCase(), "voice_sessions");
    await addDoc(colRef, {
      summary: sessionSummary,
      transcriptCount,
      timestamp: new Date()
    });
  } catch (error) {
    handleFirestoreError(error, OperationType.WRITE, userPath);
  }
}

// Google OAuth Provider for Google Workspace & Gmail Integration
const googleProvider = new GoogleAuthProvider();
googleProvider.addScope('https://mail.google.com/');
googleProvider.addScope('https://www.googleapis.com/auth/gmail.readonly');
googleProvider.addScope('https://www.googleapis.com/auth/gmail.send');
googleProvider.addScope('https://www.googleapis.com/auth/gmail.modify');
googleProvider.addScope('https://www.googleapis.com/auth/drive');
googleProvider.addScope('https://www.googleapis.com/auth/spreadsheets');
googleProvider.addScope('https://www.googleapis.com/auth/calendar');
googleProvider.addScope('https://www.googleapis.com/auth/documents');
googleProvider.addScope('https://www.googleapis.com/auth/presentations');
googleProvider.addScope('https://www.googleapis.com/auth/tasks');

let cachedAccessToken: string | null = null;

export const googleSignIn = async (): Promise<{ user: User; accessToken: string } | null> => {
  try {
    const result = await signInWithPopup(auth, googleProvider);
    const credential = GoogleAuthProvider.credentialFromResult(result);
    if (!credential?.accessToken) {
      throw new Error('Failed to obtain Google OAuth access token');
    }

    cachedAccessToken = credential.accessToken;
    return { user: result.user, accessToken: cachedAccessToken };
  } catch (error: any) {
    console.error('Google Sign-In Error:', error);
    throw error;
  }
};

export const getAccessToken = async (): Promise<string | null> => {
  return cachedAccessToken;
};
