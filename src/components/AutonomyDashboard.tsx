import React, { useState, useEffect } from "react";
import {
  Sparkles,
  Layers,
  Check,
  Send,
  Terminal,
  ShieldAlert,
  Mail,
  MessageSquare,
  LogOut,
  ExternalLink,
  AlertTriangle,
} from "lucide-react";

interface MissionStepData {
  id: string;
  description: string;
  action: string;
  args: any;
  status: string;
  result?: any;
  error?: string;
  verification?: any;
  confirmation_required?: boolean;
}

interface MissionData {
  id: string;
  goal: string;
  state: string;
  steps: MissionStepData[];
  current_step_index: number;
  current_step?: MissionStepData;
  progress_percent: number;
  failures: any[];
  recovery_attempts: any[];
  final_summary?: any;
}

interface StatusInfo {
  status: "CONNECTED" | "DISCONNECTED" | "AUTH_REQUIRED" | "ERROR" | "MOCK_MODE";
  authenticated: boolean;
  user_email?: string;
  phone_number_id?: string;
  provider: string;
  message?: string;
}

export const AutonomyDashboard: React.FC = () => {
  const [prompt, setPrompt] = useState("");
  const [loading, setLoading] = useState(false);
  const [missionData, setMissionData] = useState<MissionData | null>(null);
  const [activeMissionId, setActiveMissionId] = useState<string | null>(null);
  const [gmailStatus, setGmailStatus] = useState<StatusInfo | null>(null);
  const [whatsappStatus, setWhatsappStatus] = useState<StatusInfo | null>(null);
  const [authUrlLoading, setAuthUrlLoading] = useState(false);

  const loadStatuses = async () => {
    try {
      const gRes = await fetch("/api/gmail/status");
      if (gRes.ok) setGmailStatus(await gRes.json());
    } catch {}
    try {
      const wRes = await fetch("/api/whatsapp/status");
      if (wRes.ok) setWhatsappStatus(await wRes.json());
    } catch {}
  };

  useEffect(() => {
    loadStatuses();
  }, []);

  // Poll for status updates when an active mission exists
  useEffect(() => {
    if (!activeMissionId) return;
    const interval = setInterval(async () => {
      try {
        const res = await fetch(`/api/missions/${activeMissionId}`);
        if (res.ok) {
          const data = await res.json();
          setMissionData(data);
        }
      } catch (err) {
        console.error("Error polling mission status:", err);
      }
    }, 1500);
    return () => clearInterval(interval);
  }, [activeMissionId]);

  const handleSubmitGoal = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!prompt.trim() || loading) return;
    setLoading(true);
    try {
      const res = await fetch("/api/missions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ goal: prompt }),
      });
      if (res.ok) {
        const data = await res.json();
        setMissionData(data);
        setActiveMissionId(data.id);
      }
    } catch (err) {
      console.error("Failed to submit mission goal:", err);
    } finally {
      setLoading(false);
    }
  };

  const handleApproveStep = async () => {
    if (!activeMissionId) return;
    try {
      const res = await fetch(`/api/missions/${activeMissionId}/approve`, { method: "POST" });
      if (res.ok) {
        const data = await res.json();
        setMissionData(data);
      }
    } catch (err) {
      console.error("Failed to approve step:", err);
    }
  };

  const handleConnectGmail = async () => {
    setAuthUrlLoading(true);
    try {
      const res = await fetch("/api/gmail/auth-url");
      const data = await res.json();
      if (data.success && data.auth_url) {
        window.open(data.auth_url, "_blank", "width=600,height=700");
      } else {
        alert(data.message || "Failed to generate Google OAuth consent URL.");
      }
    } catch (err) {
      alert("Error contacting ERA backend for Gmail OAuth.");
    } finally {
      setAuthUrlLoading(false);
    }
  };

  const handleDisconnectGmail = async () => {
    if (!confirm("Are you sure you want to disconnect your Gmail account from ERA?")) return;
    await fetch("/api/gmail/disconnect", { method: "POST" });
    loadStatuses();
  };

  const renderStatusBadge = (statusObj: StatusInfo | null, type: "Gmail" | "WhatsApp") => {
    if (!statusObj) return null;
    const st = statusObj.status;

    if (st === "CONNECTED") {
      return (
        <div className="flex items-center space-x-2 bg-emerald-500/10 border border-emerald-500/30 px-3 py-1.5 rounded-lg text-xs">
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
          <span className="font-semibold text-emerald-400">
            {type}: Connected {statusObj.user_email ? `(${statusObj.user_email})` : ""}
          </span>
          {type === "Gmail" && (
            <button onClick={handleDisconnectGmail} title="Disconnect" className="ml-1 text-slate-400 hover:text-rose-400 transition-colors">
              <LogOut className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      );
    }

    if (st === "AUTH_REQUIRED" || st === "DISCONNECTED") {
      return (
        <div className="flex items-center space-x-2 bg-amber-500/10 border border-amber-500/30 px-3 py-1.5 rounded-lg text-xs">
          <span className="w-2 h-2 rounded-full bg-amber-400" />
          <span className="font-semibold text-amber-400">{type}: Auth Required</span>
          {type === "Gmail" && (
            <button onClick={handleConnectGmail} disabled={authUrlLoading} className="ml-1 px-2 py-0.5 bg-cyan-600 hover:bg-cyan-500 text-white rounded text-[11px] font-medium transition-colors flex items-center space-x-1">
              <ExternalLink className="w-3 h-3" />
              <span>Connect</span>
            </button>
          )}
        </div>
      );
    }

    if (st === "MOCK_MODE") {
      return (
        <div className="flex items-center space-x-2 bg-purple-500/10 border border-purple-500/30 px-3 py-1.5 rounded-lg text-xs text-purple-300">
          <span className="w-2 h-2 rounded-full bg-purple-400" />
          <span className="font-semibold">{type}: Mock Mode</span>
        </div>
      );
    }

    return (
      <div className="flex items-center space-x-2 bg-rose-500/10 border border-rose-500/30 px-3 py-1.5 rounded-lg text-xs text-rose-400">
        <AlertTriangle className="w-3.5 h-3.5" />
        <span className="font-semibold">{type}: Error</span>
      </div>
    );
  };

  const stages = ["UNDERSTAND", "PLAN", "OBSERVE", "ACT", "VERIFY", "RECOVER", "COMPLETE"];
  const currentStage = missionData?.state || "UNDERSTAND";

  return (
    <div className="p-6 bg-slate-900 text-slate-100 rounded-xl space-y-6 border border-slate-800 shadow-2xl">
      {/* Header & Connectivity Toolbar */}
      <div className="flex flex-col md:flex-row md:items-center justify-between border-b border-slate-800 pb-4 gap-4">
        <div className="flex items-center space-x-3">
          <div className="p-2 bg-cyan-500/10 text-cyan-400 rounded-lg">
            <Sparkles className="w-6 h-6" />
          </div>
          <div>
            <h2 className="text-xl font-bold tracking-tight">ERA Mission Engine</h2>
            <p className="text-sm text-slate-400">"User → Goal → Observe → Plan → Act → Verify → Recover → Complete → Learn"</p>
          </div>
        </div>

        {/* Real Provider Connectivity Status Badges */}
        <div className="flex flex-wrap items-center gap-2">
          {renderStatusBadge(gmailStatus, "Gmail")}
          {renderStatusBadge(whatsappStatus, "WhatsApp")}
        </div>
      </div>

      {/* Goal Submission Form */}
      <form onSubmit={handleSubmitGoal} className="space-y-3">
        <label className="block text-sm font-medium text-slate-300">Submit High-Level Mission Goal</label>
        <div className="flex space-x-2">
          <input
            type="text"
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder="e.g. ERA, prepare my presentation / ERA, check Gmail and WhatsApp..."
            className="flex-1 px-4 py-2.5 bg-slate-800/80 border border-slate-700 rounded-lg text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-cyan-500"
          />
          <button
            type="submit"
            disabled={loading}
            className="px-5 py-2.5 bg-cyan-600 hover:bg-cyan-500 text-white font-medium rounded-lg transition-colors flex items-center space-x-2 disabled:opacity-50"
          >
            <Send className="w-4 h-4" />
            <span>{loading ? "Planning..." : "Start Mission"}</span>
          </button>
        </div>
      </form>

      {/* Autonomous Stage Timeline */}
      <div className="bg-slate-850 p-4 rounded-lg border border-slate-800">
        <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">
          Flagship Autonomous Loop Stage
        </h3>
        <div className="grid grid-cols-7 gap-2">
          {stages.map((stage) => {
            const isActive = currentStage === stage;
            return (
              <div
                key={stage}
                className={`p-2.5 text-center rounded-lg border text-xs font-semibold tracking-wide transition-all ${
                  isActive
                    ? "bg-cyan-500/20 text-cyan-300 border-cyan-500 shadow-lg shadow-cyan-500/10 animate-pulse"
                    : "bg-slate-800/40 text-slate-500 border-slate-800"
                }`}
              >
                {stage}
              </div>
            );
          })}
        </div>
      </div>

      {/* Mission Execution Grid */}
      {missionData && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Column 1: Progress & Steps */}
          <div className="lg:col-span-1 space-y-4">
            <div className="bg-slate-800/50 p-4 rounded-lg border border-slate-800 space-y-3">
              <h3 className="text-sm font-semibold text-slate-200 flex items-center space-x-2">
                <Layers className="w-4 h-4 text-cyan-400" />
                <span>Mission Goal</span>
              </h3>
              <div className="text-xs text-slate-300 bg-slate-900/60 p-3 rounded border border-slate-800">
                {missionData.goal}
              </div>
              <div className="flex justify-between items-center text-xs text-slate-400">
                <span>Progress:</span>
                <span className="font-bold text-cyan-400">{missionData.progress_percent}%</span>
              </div>
              <div className="w-full bg-slate-800 h-2 rounded-full overflow-hidden">
                <div
                  className="bg-cyan-500 h-full transition-all duration-500"
                  style={{ width: `${missionData.progress_percent}%` }}
                />
              </div>
            </div>

            {/* Steps List */}
            <div className="bg-slate-800/50 p-4 rounded-lg border border-slate-800 space-y-3">
              <h3 className="text-sm font-semibold text-slate-200">Execution Plan Steps</h3>
              <div className="space-y-2 max-h-64 overflow-y-auto pr-1">
                {missionData.steps.map((step, idx) => (
                  <div
                    key={step.id || idx}
                    className="p-3 bg-slate-900/80 rounded border border-slate-800 flex items-start justify-between text-xs"
                  >
                    <div>
                      <div className="font-medium text-slate-200">{step.description}</div>
                      <div className="text-slate-400 text-[11px] mt-0.5 font-mono">
                        Action: {step.action}
                      </div>
                    </div>
                    <span
                      className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase ${
                        step.status === "SUCCESS"
                          ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                          : step.status === "RUNNING"
                          ? "bg-cyan-500/10 text-cyan-400 border border-cyan-500/20 animate-pulse"
                          : step.status === "WAITING_FOR_CONFIRMATION"
                          ? "bg-amber-500/10 text-amber-400 border border-amber-500/20"
                          : "bg-slate-800 text-slate-400"
                      }`}
                    >
                      {step.status}
                    </span>
                  </div>
                ))}
              </div>

              {/* Confirmation Gate Alert */}
              {missionData.current_step?.status === "WAITING_FOR_CONFIRMATION" && (
                <div className="p-3 bg-amber-500/10 border border-amber-500/30 rounded-lg space-y-2">
                  <div className="flex items-center space-x-2 text-amber-400 text-xs font-semibold">
                    <ShieldAlert className="w-4 h-4" />
                    <span>External Side-Effect Action Requires Confirmation</span>
                  </div>
                  <div className="text-xs text-slate-300 font-mono">
                    Action: {missionData.current_step.action}
                  </div>
                  <button
                    onClick={handleApproveStep}
                    className="w-full py-1.5 bg-amber-600 hover:bg-amber-500 text-white rounded text-xs font-semibold transition-colors flex items-center justify-center space-x-1"
                  >
                    <Check className="w-3.5 h-3.5" />
                    <span>Confirm & Authorize Action</span>
                  </button>
                </div>
              )}
            </div>
          </div>

          {/* Column 2 & 3: Mission Trace & Summary */}
          <div className="lg:col-span-2 space-y-4">
            <div className="bg-slate-800/50 p-4 rounded-lg border border-slate-800 space-y-3">
              <h3 className="text-sm font-semibold text-slate-200 flex items-center space-x-2">
                <Terminal className="w-4 h-4 text-cyan-400" />
                <span>Execution Trace & Verifications</span>
              </h3>
              <div className="bg-slate-950 p-4 rounded-lg font-mono text-xs text-slate-300 max-h-96 overflow-y-auto space-y-2 border border-slate-800">
                {missionData.steps.map((step, idx) => (
                  <div key={idx} className="border-b border-slate-850 pb-2 space-y-1">
                    <div className="flex items-center justify-between text-cyan-400 font-semibold">
                      <span>[{step.status}] {step.description}</span>
                    </div>
                    {step.result && (
                      <div className="text-slate-400 text-[11px]">
                        <span className="text-slate-500 font-medium">Result: </span>
                        {JSON.stringify(step.result)}
                      </div>
                    )}
                    {step.verification && (
                      <div className="text-emerald-400 text-[11px]">
                        <span className="text-slate-500 font-medium">Verification: </span>
                        {step.verification.reason || "Empirical check passed"}
                      </div>
                    )}
                    {step.error && (
                      <div className="text-rose-400 text-[11px]">
                        <span className="text-slate-500 font-medium">Error: </span>
                        {step.error}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>

            {/* Final Completion Report */}
            {missionData.final_summary && (
              <div className="bg-emerald-950/20 border border-emerald-500/30 p-4 rounded-lg space-y-2">
                <h4 className="text-xs font-bold text-emerald-400 uppercase tracking-wider">
                  Final Mission Completion Report
                </h4>
                <div className="text-xs text-slate-300 space-y-1">
                  <div><span className="font-semibold text-slate-400">Goal:</span> {missionData.final_summary.goal}</div>
                  <div><span className="font-semibold text-slate-400">Completed Steps:</span> {missionData.final_summary.completed_steps?.join(" → ")}</div>
                  <div><span className="font-semibold text-slate-400">Duration:</span> {missionData.final_summary.duration}s</div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
