import fetch from "node-fetch";

const OUTCOME_ENGINE_URL = process.env.ERA_AGENT_URL || "http://127.0.0.1:8000";

export interface OutcomeTaskStatus {
  success: boolean;
  task_id: string;
  prompt: string;
  status: string;
  objective: string;
  workflow_type?: string;
  graph_summary: {
    total_tasks: number;
    completed_tasks: number;
    failed_tasks: number;
    is_paused: boolean;
    is_cancelled: boolean;
    progress_percent: number;
    nodes: any[];
  };
  why_trace: Array<{
    stage: string;
    goal: string;
    action: string;
    observed: string;
    decision: string;
    status: string;
  }>;
  final_report?: any;
}

export interface MissionStatus {
  id: string;
  goal: string;
  state: string;
  steps: Array<{
    id: string;
    description: string;
    action: string;
    status: string;
    result?: any;
    error?: string;
    verification?: any;
    confirmation_required?: boolean;
  }>;
  current_step_index: number;
  progress_percent: number;
  final_summary?: any;
}

export async function submitOutcomeGoal(prompt: string): Promise<OutcomeTaskStatus | null> {
  try {
    const res = await fetch(`${OUTCOME_ENGINE_URL}/v1/outcome/submit`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt }),
    });
    if (!res.ok) return null;
    return (await res.json()) as OutcomeTaskStatus;
  } catch (err) {
    console.error("Failed to submit outcome goal to ERA Agent:", err);
    return null;
  }
}

export async function fetchOutcomeTaskStatus(taskId: string): Promise<OutcomeTaskStatus | null> {
  try {
    const res = await fetch(`${OUTCOME_ENGINE_URL}/v1/outcome/status/${taskId}`);
    if (!res.ok) return null;
    return (await res.json()) as OutcomeTaskStatus;
  } catch (err) {
    console.error(`Failed to fetch outcome task status for ${taskId}:`, err);
    return null;
  }
}

export async function approveOutcomeTask(taskId: string): Promise<OutcomeTaskStatus | null> {
  try {
    const res = await fetch(`${OUTCOME_ENGINE_URL}/v1/outcome/approve/${taskId}`, { method: "POST" });
    if (!res.ok) return null;
    return (await res.json()) as OutcomeTaskStatus;
  } catch (err) {
    console.error(`Failed to approve task ${taskId}:`, err);
    return null;
  }
}

export async function pauseOutcomeTask(taskId: string): Promise<OutcomeTaskStatus | null> {
  try {
    const res = await fetch(`${OUTCOME_ENGINE_URL}/v1/outcome/pause/${taskId}`, { method: "POST" });
    if (!res.ok) return null;
    return (await res.json()) as OutcomeTaskStatus;
  } catch (err) {
    console.error(`Failed to pause task ${taskId}:`, err);
    return null;
  }
}

export async function resumeOutcomeTask(taskId: string): Promise<OutcomeTaskStatus | null> {
  try {
    const res = await fetch(`${OUTCOME_ENGINE_URL}/v1/outcome/resume/${taskId}`, { method: "POST" });
    if (!res.ok) return null;
    return (await res.json()) as OutcomeTaskStatus;
  } catch (err) {
    console.error(`Failed to resume task ${taskId}:`, err);
    return null;
  }
}

export async function cancelOutcomeTask(taskId: string): Promise<OutcomeTaskStatus | null> {
  try {
    const res = await fetch(`${OUTCOME_ENGINE_URL}/v1/outcome/cancel/${taskId}`, { method: "POST" });
    if (!res.ok) return null;
    return (await res.json()) as OutcomeTaskStatus;
  } catch (err) {
    console.error(`Failed to cancel task ${taskId}:`, err);
    return null;
  }
}

// ERA Mission Engine API Client Functions
export async function createMission(goal: string, context: any = {}): Promise<MissionStatus | null> {
  try {
    const res = await fetch(`${OUTCOME_ENGINE_URL}/api/missions`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ goal, context }),
    });
    if (!res.ok) return null;
    return (await res.json()) as MissionStatus;
  } catch (err) {
    console.error("Failed to create mission in ERA Agent:", err);
    return null;
  }
}

export async function fetchMission(missionId: string): Promise<MissionStatus | null> {
  try {
    const res = await fetch(`${OUTCOME_ENGINE_URL}/api/missions/${missionId}`);
    if (!res.ok) return null;
    return (await res.json()) as MissionStatus;
  } catch (err) {
    console.error(`Failed to fetch mission ${missionId}:`, err);
    return null;
  }
}

export async function approveMissionStep(missionId: string): Promise<MissionStatus | null> {
  try {
    const res = await fetch(`${OUTCOME_ENGINE_URL}/api/missions/${missionId}/approve`, { method: "POST" });
    if (!res.ok) return null;
    return (await res.json()) as MissionStatus;
  } catch (err) {
    console.error(`Failed to approve step for mission ${missionId}:`, err);
    return null;
  }
}

// Gmail & WhatsApp Connection Status API Client Functions
export async function fetchGmailStatus(): Promise<any> {
  try {
    const res = await fetch(`${OUTCOME_ENGINE_URL}/api/gmail/status`);
    if (!res.ok) return { status: "DISCONNECTED", authenticated: false };
    return await res.json();
  } catch (err) {
    return { status: "DISCONNECTED", authenticated: false };
  }
}

export async function fetchGmailAuthUrl(): Promise<any> {
  try {
    const res = await fetch(`${OUTCOME_ENGINE_URL}/api/gmail/auth-url`);
    if (!res.ok) return { success: false, message: "Failed to connect to ERA Agent." };
    return await res.json();
  } catch (err) {
    return { success: false, message: "Error contacting ERA Agent." };
  }
}

export async function disconnectGmail(): Promise<any> {
  try {
    const res = await fetch(`${OUTCOME_ENGINE_URL}/api/gmail/disconnect`, { method: "POST" });
    if (!res.ok) return { success: false };
    return await res.json();
  } catch (err) {
    return { success: false };
  }
}

export async function fetchWhatsAppStatus(): Promise<any> {
  try {
    const res = await fetch(`${OUTCOME_ENGINE_URL}/api/whatsapp/status`);
    if (!res.ok) return { status: "DISCONNECTED", authenticated: false };
    return await res.json();
  } catch (err) {
    return { status: "DISCONNECTED", authenticated: false };
  }
}

export async function fetchComputerState(): Promise<any> {
  try {
    const res = await fetch(`${OUTCOME_ENGINE_URL}/intelligence/computer`);
    if (!res.ok) return null;
    return await res.json();
  } catch (err) {
    console.error("Failed to fetch computer state from ERA Agent:", err);
    return null;
  }
}

