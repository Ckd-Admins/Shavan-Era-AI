"""Dynamic Task Graph Execution Engine for ERA Outcome Engine."""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional
from .models import ConfidenceLevel, OutcomeContract, RiskLevel, TaskNode, TaskStatus


class TaskGraph:
    """Manages dynamic task DAG execution, state transitions, and graph mutations."""

    def __init__(self, goal_contract: OutcomeContract):
        self.contract = goal_contract
        self.nodes: Dict[str, TaskNode] = {}
        self.execution_order: List[str] = []
        self.current_task_id: Optional[str] = None
        self.is_paused: bool = False
        self.is_cancelled: bool = False

    def add_node(self, node: TaskNode) -> None:
        self.nodes[node.id] = node
        if node.id not in self.execution_order:
            self.execution_order.append(node.id)

    @classmethod
    def create_for_contract(cls, contract: OutcomeContract, stack_info: Dict[str, Any]) -> TaskGraph:
        graph = cls(contract)
        wf = contract.workflow_type

        # ----------------------------------------------------------------------
        # WORKFLOW 1: LAPTOP MAINTENANCE
        # ----------------------------------------------------------------------
        if wf == "laptop_maintenance":
            graph.add_node(
                TaskNode(
                    id="observe_laptop_status",
                    title="1. Observe System & Software Update Status",
                    description="Scans operating system update mechanisms and pending software updates.",
                    action_type="observe_laptop_status",
                    priority=1,
                    risk_level=RiskLevel.SAFE,
                    verification_strategy="exit_code",
                )
            )
            graph.add_node(
                TaskNode(
                    id="request_update_approval",
                    title="2. Request Approval for Package Updates",
                    description="Presents available updates to the user for explicit confirmation before installation.",
                    dependencies=["observe_laptop_status"],
                    action_type="request_approval",
                    priority=2,
                    risk_level=RiskLevel.HIGH_RISK,
                    verification_strategy="exit_code",
                )
            )
            graph.add_node(
                TaskNode(
                    id="install_software_updates",
                    title="3. Install Permitted Software Updates",
                    description="Executes system update installation via winget for authorized packages.",
                    dependencies=["request_update_approval"],
                    action_type="install_software_updates",
                    priority=3,
                    risk_level=RiskLevel.HIGH_RISK,
                    verification_strategy="system_update_installed",
                )
            )
            graph.add_node(
                TaskNode(
                    id="verify_laptop_maintenance",
                    title="4. Verify Final Laptop Update Status",
                    description="Re-observes system update status to confirm successful installation.",
                    dependencies=["install_software_updates"],
                    action_type="verify_laptop_updates",
                    priority=4,
                    risk_level=RiskLevel.SAFE,
                    verification_strategy="multi_factor",
                    verification_params={"criteria": contract.acceptance_criteria},
                )
            )

        # ----------------------------------------------------------------------
        # WORKFLOW 2: GOVERNMENT FORM HELPER
        # ----------------------------------------------------------------------
        elif wf == "government_form":
            graph.add_node(
                TaskNode(
                    id="open_form_website",
                    title="1. Open Official Form Web Portal",
                    description="Launches browser and navigates to the requested government form URL.",
                    action_type="browser_open_form",
                    priority=1,
                    risk_level=RiskLevel.SAFE,
                    verification_strategy="exit_code",
                    params={"url": "https://official.gov/form-portal"},
                )
            )
            graph.add_node(
                TaskNode(
                    id="fill_form_fields",
                    title="2. Fill Form Fields with User Information",
                    description="Enters authorized user-provided information into specified form fields.",
                    dependencies=["open_form_website"],
                    action_type="fill_form_fields",
                    priority=2,
                    risk_level=RiskLevel.REVERSIBLE,
                    verification_strategy="form_data_matched",
                    params={"form_data": {"applicant_name": "Verified User", "document_type": "Application"}},
                )
            )
            graph.add_node(
                TaskNode(
                    id="review_form_submission",
                    title="3. User Review Before Final Submission",
                    description="Pauses for explicit user verification and approval before submitting the form.",
                    dependencies=["fill_form_fields"],
                    action_type="request_approval",
                    priority=3,
                    risk_level=RiskLevel.HIGH_RISK,
                    verification_strategy="exit_code",
                )
            )
            graph.add_node(
                TaskNode(
                    id="submit_form",
                    title="4. Submit Form & Verify Receipt",
                    description="Submits the form after explicit approval and checks for confirmation.",
                    dependencies=["review_form_submission"],
                    action_type="submit_form",
                    priority=4,
                    risk_level=RiskLevel.HIGH_RISK,
                    verification_strategy="multi_factor",
                    verification_params={"criteria": contract.acceptance_criteria},
                )
            )

        # ----------------------------------------------------------------------
        # WORKFLOW 3: FIX CODING ERROR
        # ----------------------------------------------------------------------
        elif wf == "fix_coding_error":
            graph.add_node(
                TaskNode(
                    id="inspect_workspace",
                    title="1. Inspect Project Codebase",
                    description="Scans project files and discovers source code structure.",
                    action_type="inspect_workspace",
                    priority=1,
                    risk_level=RiskLevel.SAFE,
                    verification_strategy="exit_code",
                )
            )
            graph.add_node(
                TaskNode(
                    id="run_diagnostics",
                    title="2. Run Automated Diagnostics & Tests",
                    description="Executes unittest suite to identify reproducible errors.",
                    dependencies=["inspect_workspace"],
                    action_type="run_diagnostics",
                    priority=2,
                    risk_level=RiskLevel.SAFE,
                    verification_strategy="exit_code",
                )
            )
            graph.add_node(
                TaskNode(
                    id="apply_code_repair",
                    title="3. Apply Targeted Code Repair",
                    description="Modifies source code to fix diagnosed syntax or logical errors.",
                    dependencies=["run_diagnostics"],
                    action_type="apply_code_repair",
                    priority=3,
                    risk_level=RiskLevel.REVERSIBLE,
                    verification_strategy="file_exists",
                    params={"file_path": "main.py"},
                )
            )
            graph.add_node(
                TaskNode(
                    id="verify_code_fix",
                    title="4. Re-run Tests & Verify Repair",
                    description="Confirms that tests pass cleanly and no regressions were introduced.",
                    dependencies=["apply_code_repair"],
                    action_type="verify_code_fix",
                    priority=4,
                    risk_level=RiskLevel.SAFE,
                    verification_strategy="file_exists",
                    params={"file_path": "main.py"},
                )
            )

        # ----------------------------------------------------------------------
        # WORKFLOW 4: GAME CREATION (Temple Run / Canvas Arcade Games)
        # ----------------------------------------------------------------------
        elif wf == "game_creation":
            graph.add_node(
                TaskNode(
                    id="inspect_workspace",
                    title="1. Inspect Environment & Workspace",
                    description="Scans workspace directory for existing files.",
                    action_type="inspect_workspace",
                    priority=1,
                    risk_level=RiskLevel.SAFE,
                    verification_strategy="exit_code",
                )
            )
            graph.add_node(
                TaskNode(
                    id="create_project_files",
                    title="2. Generate Playable 3D/2D Game Engine Files",
                    description=f"Generates deliverables: {', '.join(contract.deliverables)}",
                    dependencies=["inspect_workspace"],
                    action_type="generate_code_files",
                    priority=2,
                    risk_level=RiskLevel.REVERSIBLE,
                    verification_strategy="file_exists",
                    params={"deliverables": contract.deliverables, "stack": stack_info, "workflow_type": "game_creation"},
                )
            )
            graph.add_node(
                TaskNode(
                    id="run_application",
                    title="3. Launch Local Game Server",
                    description="Starts background web server on port 8080.",
                    dependencies=["create_project_files"],
                    action_type="run_command",
                    priority=3,
                    risk_level=RiskLevel.SAFE,
                    params={"command": "python -m http.server 8080", "is_background": True},
                    verification_strategy="exit_code",
                )
            )
            graph.add_node(
                TaskNode(
                    id="launch_game_in_browser",
                    title="4. Launch Game in Browser for Immediate Gameplay",
                    description="Opens the game directly in the default browser at http://127.0.0.1:8080.",
                    dependencies=["run_application"],
                    action_type="open_in_browser",
                    priority=4,
                    risk_level=RiskLevel.SAFE,
                    params={"url": "http://127.0.0.1:8080"},
                    verification_strategy="exit_code",
                )
            )
            graph.add_node(
                TaskNode(
                    id="verify_outcome",
                    title="5. Multi-Factor Verification of Game",
                    description="Probes HTTP server and verifies game files and HTTP 200 OK status.",
                    dependencies=["launch_game_in_browser"],
                    action_type="verify_outcome",
                    priority=5,
                    risk_level=RiskLevel.SAFE,
                    verification_strategy="multi_factor",
                    verification_params={"criteria": contract.acceptance_criteria, "url": "http://127.0.0.1:8080"},
                )
            )

        # ----------------------------------------------------------------------
        # WORKFLOW 5: WEBSITE CREATION (Startup / AI App)
        # ----------------------------------------------------------------------
        elif wf == "website_creation":
            graph.add_node(
                TaskNode(
                    id="inspect_workspace",
                    title="1. Inspect Environment & Workspace",
                    description="Scans workspace directory for existing files.",
                    action_type="inspect_workspace",
                    priority=1,
                    risk_level=RiskLevel.SAFE,
                    verification_strategy="exit_code",
                )
            )
            graph.add_node(
                TaskNode(
                    id="create_project_files",
                    title="2. Generate Responsive Website Files",
                    description=f"Generates deliverables: {', '.join(contract.deliverables)}",
                    dependencies=["inspect_workspace"],
                    action_type="generate_code_files",
                    priority=2,
                    risk_level=RiskLevel.REVERSIBLE,
                    verification_strategy="file_exists",
                    params={"deliverables": contract.deliverables, "stack": stack_info},
                )
            )
            graph.add_node(
                TaskNode(
                    id="run_application",
                    title="3. Launch Local HTTP Development Server",
                    description="Starts background web server on port 8080.",
                    dependencies=["create_project_files"],
                    action_type="run_command",
                    priority=3,
                    risk_level=RiskLevel.SAFE,
                    params={"command": "python -m http.server 8080", "is_background": True},
                    verification_strategy="exit_code",
                )
            )
            graph.add_node(
                TaskNode(
                    id="verify_outcome",
                    title="4. Multi-Factor Verification of Website",
                    description="Probes HTTP server and verifies HTML/CSS/JS stability.",
                    dependencies=["run_application"],
                    action_type="verify_outcome",
                    priority=4,
                    risk_level=RiskLevel.SAFE,
                    verification_strategy="multi_factor",
                    verification_params={"criteria": contract.acceptance_criteria, "url": "http://127.0.0.1:8080"},
                )
            )


        # ----------------------------------------------------------------------
        # GENERIC WORKFLOW FALLBACK
        # ----------------------------------------------------------------------
        else:
            graph.add_node(
                TaskNode(
                    id="inspect_workspace",
                    title="1. Inspect Environment & Workspace",
                    description="Scans files and available tools.",
                    action_type="inspect_workspace",
                    priority=1,
                    risk_level=RiskLevel.SAFE,
                )
            )
            if contract.deliverables:
                graph.add_node(
                    TaskNode(
                        id="create_project_files",
                        title="2. Generate Core Deliverable Files",
                        description=f"Creates: {', '.join(contract.deliverables)}",
                        dependencies=["inspect_workspace"],
                        action_type="generate_code_files",
                        priority=2,
                        risk_level=RiskLevel.REVERSIBLE,
                        params={"deliverables": contract.deliverables, "stack": stack_info},
                    )
                )
            graph.add_node(
                TaskNode(
                    id="verify_outcome",
                    title="3. Verify Outcome Criteria",
                    description="Checks acceptance criteria.",
                    dependencies=["create_project_files"] if contract.deliverables else ["inspect_workspace"],
                    action_type="verify_outcome",
                    priority=3,
                    risk_level=RiskLevel.SAFE,
                    verification_strategy="multi_factor",
                    verification_params={"criteria": contract.acceptance_criteria},
                )
            )

        return graph

    def get_next_executable_node(self) -> Optional[TaskNode]:
        """Finds highest-priority pending task whose dependencies are completed."""
        if self.is_paused or self.is_cancelled:
            return None

        candidate_nodes = []
        for node in self.nodes.values():
            if node.status not in [TaskStatus.PLANNING, TaskStatus.QUEUED]:
                continue

            # Check dependencies
            deps_ok = True
            for dep_id in node.dependencies:
                dep_node = self.nodes.get(dep_id)
                if not dep_node or dep_node.status != TaskStatus.COMPLETED:
                    deps_ok = False
                    break

            if deps_ok:
                candidate_nodes.append(node)

        if not candidate_nodes:
            return None

        # Sort by priority ascending (1 highest)
        candidate_nodes.sort(key=lambda n: n.priority)
        return candidate_nodes[0]

    def insert_recovery_node(self, failed_node_id: str, fix_action: str, fix_params: Dict[str, Any]) -> TaskNode:
        """Dynamically mutates graph to inject a repair node before retrying."""
        recovery_id = f"recover_{failed_node_id}_{int(time.time())}"
        failed_node = self.nodes[failed_node_id]
        failed_node.status = TaskStatus.RECOVERING

        recovery_node = TaskNode(
            id=recovery_id,
            title=f"Self-Recovery Fix for {failed_node.title}",
            description=f"Applies fix action '{fix_action}' to resolve failure.",
            dependencies=[dep for dep in failed_node.dependencies if dep != recovery_id],
            priority=failed_node.priority,
            action_type=fix_action,
            params=fix_params,
            risk_level=RiskLevel.REVERSIBLE,
        )

        self.add_node(recovery_node)
        if recovery_id not in failed_node.dependencies:
            failed_node.dependencies.append(recovery_id)
        failed_node.status = TaskStatus.PLANNING

        return recovery_node

    def get_summary(self) -> Dict[str, Any]:
        total = len(self.nodes)
        completed = sum(1 for n in self.nodes.values() if n.status == TaskStatus.COMPLETED)
        failed = sum(1 for n in self.nodes.values() if n.status in [TaskStatus.FAILED, TaskStatus.BLOCKED])
        return {
            "total_tasks": total,
            "completed_tasks": completed,
            "failed_tasks": failed,
            "is_paused": self.is_paused,
            "is_cancelled": self.is_cancelled,
            "progress_percent": int((completed / total) * 100) if total > 0 else 0,
            "nodes": [n.model_dump() for n in self.nodes.values()],
        }
