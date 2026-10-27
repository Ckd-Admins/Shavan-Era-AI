"""Comprehensive Test Suite for ERA Autonomous Goal Execution Engine."""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from era_agent.outcome_engine.checkpoint_manager import CheckpointManager
from era_agent.outcome_engine.coding_engine import CodingEngine
from era_agent.outcome_engine.goal_interpreter import GoalInterpreter
from era_agent.outcome_engine.models import AgentMode, RiskLevel, TaskNode, TaskStatus
from era_agent.outcome_engine.orchestrator import OutcomeEngineOrchestrator
from era_agent.outcome_engine.recovery_engine import SelfRecoveryEngine
from era_agent.outcome_engine.safety_policy import SafetyPolicy
from era_agent.outcome_engine.state_observer import StateObserver
from era_agent.outcome_engine.task_graph import TaskGraph
from era_agent.outcome_engine.tech_selector import TechSelector
from era_agent.outcome_engine.verifier import Verifier


class TestOutcomeEngine(unittest.TestCase):
    """Test suite covering the 5 engines, persistence, safety, and 4 real-world workflows."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.workspace_path = str(Path(self.test_dir) / "workspace")
        Path(self.workspace_path).mkdir(parents=True, exist_ok=True)
        self.orchestrator = OutcomeEngineOrchestrator(self.workspace_path, mode=AgentMode.SUPERVISED)

    def tearDown(self):
        self.orchestrator.coding_engine.close()
        shutil.rmtree(self.test_dir, ignore_errors=True)


    # --------------------------------------------------------------------------
    # 1. OBSERVE ENGINE TESTS
    # --------------------------------------------------------------------------
    def test_observe_engine_capture_and_mismatch(self):
        # Create a sample file
        test_file = Path(self.workspace_path) / "sample.py"
        test_file.write_text("print('test')", encoding="utf-8")

        state = StateObserver.capture_state(self.workspace_path)
        self.assertIn("sample.py", state.existing_files)
        self.assertIsInstance(state.running_processes, list)

        # Mismatch evaluation
        expected_valid = {"file": "sample.py"}
        eval_valid = StateObserver.evaluate_state_mismatch(expected_valid, state)
        self.assertFalse(eval_valid["has_mismatch"])

        expected_missing = {"file": "nonexistent.py"}
        eval_missing = StateObserver.evaluate_state_mismatch(expected_missing, state)
        self.assertTrue(eval_missing["has_mismatch"])

    # --------------------------------------------------------------------------
    # 2. PLAN ENGINE TESTS
    # --------------------------------------------------------------------------
    def test_plan_engine_goal_interpretation_and_dag(self):
        # Goal 1: Website creation
        contract_web = GoalInterpreter.interpret("ERA, build a complete responsive website for my startup.")
        self.assertEqual(contract_web.workflow_type, "website_creation")
        self.assertIn("index.html", contract_web.deliverables)

        graph_web = TaskGraph.create_for_contract(contract_web, {"type": "HTML/CSS/JS"})
        self.assertGreaterEqual(len(graph_web.nodes), 3)

        # Goal 2: Laptop maintenance
        contract_maint = GoalInterpreter.interpret("ERA, check my laptop for available updates and install them.")
        self.assertEqual(contract_maint.workflow_type, "laptop_maintenance")
        self.assertEqual(contract_maint.risk_level, RiskLevel.HIGH_RISK)

        # Goal 3: Government form helper
        contract_form = GoalInterpreter.interpret("ERA, open the relevant government website and help me fill out this form.")
        self.assertEqual(contract_form.workflow_type, "government_form")

        # Goal 4: Fix coding error
        contract_fix = GoalInterpreter.interpret("ERA, find and fix the errors in my existing project.")
        self.assertEqual(contract_fix.workflow_type, "fix_coding_error")

    # --------------------------------------------------------------------------
    # 3. ACT & VERIFY ENGINE TESTS
    # --------------------------------------------------------------------------
    def test_act_and_verify_engine_execution(self):
        coding_engine = CodingEngine(self.workspace_path)
        verifier = Verifier(coding_engine)

        # Test write file action
        res = coding_engine.write_file("app.py", "print('hello world')\n")
        self.assertTrue(res["success"])

        # Test verify file_exists strategy
        node = TaskNode(
            id="node1",
            title="Create app.py",
            description="Writes app.py file",
            action_type="write_file",
            verification_strategy="file_exists",
            params={"file_path": "app.py"},
        )
        ver_res = verifier.verify_node_execution(node, res)
        self.assertTrue(ver_res["verified"])
        self.assertIsNotNone(node.evidence)
        self.assertTrue(node.evidence.passed)

    # --------------------------------------------------------------------------
    # 4. RECOVER ENGINE TESTS
    # --------------------------------------------------------------------------
    def test_recovery_engine_missing_module_and_graph_mutation(self):
        coding_engine = CodingEngine(self.workspace_path)
        recovery_engine = SelfRecoveryEngine(coding_engine)

        error_msg = "ModuleNotFoundError: No module named requests"
        plan = recovery_engine.diagnose_and_plan_fix("task_1", error_msg)

        self.assertTrue(plan["can_recover"])
        self.assertEqual(plan["fix_action"], "run_command")
        self.assertIn("pip install requests", plan["fix_params"]["command"])

        # Test dynamic graph recovery node insertion
        contract = GoalInterpreter.interpret("Create script")
        graph = TaskGraph.create_for_contract(contract, {})
        failed_node = graph.get_next_executable_node()
        self.assertIsNotNone(failed_node)

        rec_node = graph.insert_recovery_node(failed_node.id, plan["fix_action"], plan["fix_params"])
        self.assertIn(rec_node.id, failed_node.dependencies)

    # --------------------------------------------------------------------------
    # 5. PERMISSION & SAFETY SYSTEM TESTS
    # --------------------------------------------------------------------------
    def test_safety_policy_and_redaction(self):
        # Safe read action
        safe_node = TaskNode(id="n1", title="Read state", description="", action_type="inspect_workspace", risk_level=RiskLevel.SAFE)
        self.assertFalse(SafetyPolicy.requires_user_confirmation(safe_node, mode=AgentMode.SUPERVISED))

        # High risk action requiring approval
        risk_node = TaskNode(id="n2", title="Install update", description="", action_type="install_software_updates", risk_level=RiskLevel.HIGH_RISK)
        self.assertTrue(SafetyPolicy.requires_user_confirmation(risk_node, mode=AgentMode.SUPERVISED))

        # Sensitive log redaction
        raw_log = {"user": "admin", "password": "secret_password_123", "api_key": "xyz_key"}
        sanitized = SafetyPolicy.sanitize_log_data(raw_log)
        self.assertEqual(sanitized["password"], "[REDACTED_SENSITIVE_DATA]")
        self.assertEqual(sanitized["api_key"], "[REDACTED_SENSITIVE_DATA]")

    # --------------------------------------------------------------------------
    # 6. PERSISTENCE & RESUME TESTS
    # --------------------------------------------------------------------------
    def test_checkpoint_persistence_and_list(self):
        chk_mgr = CheckpointManager(self.workspace_path)
        contract = GoalInterpreter.interpret("Test goal")
        graph = TaskGraph.create_for_contract(contract, {})

        chk_path = chk_mgr.save_checkpoint("task_100", graph, TaskStatus.RUNNING.value)
        self.assertTrue(Path(chk_path).exists())

        loaded = chk_mgr.load_checkpoint("task_100")
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["task_id"], "task_100")

        list_chks = chk_mgr.list_checkpoints()
        self.assertEqual(len(list_chks), 1)

    # --------------------------------------------------------------------------
    # 7. AUTONOMOUS WORKFLOW END-TO-END TESTS
    # --------------------------------------------------------------------------
    def test_end_to_end_website_creation_workflow(self):
        result = self.orchestrator.submit_goal("ERA, build a complete responsive website for my startup.")
        self.assertTrue(result["success"])
        self.assertEqual(result["workflow_type"], "website_creation")

        # Check generated deliverables in workspace
        files = self.orchestrator.coding_engine.list_files()
        self.assertIn("index.html", files)
        self.assertIn("styles.css", files)
        self.assertIn("app.js", files)
        self.assertEqual(result["status"], TaskStatus.COMPLETED.value)

    def test_end_to_end_fix_coding_error_workflow(self):
        # Create a buggy test file and main file
        main_py = Path(self.workspace_path) / "main.py"
        main_py.write_text("def add(a,b):\n\treturn a+b\n", encoding="utf-8")

        result = self.orchestrator.submit_goal("ERA, find and fix the errors in my existing project.")
        self.assertTrue(result["success"])
        self.assertEqual(result["workflow_type"], "fix_coding_error")
        self.assertIn(result["status"], [TaskStatus.COMPLETED.value, TaskStatus.RUNNING.value])

    def test_pause_resume_cancel_controls(self):
        res_submit = self.orchestrator.submit_goal("ERA, build a responsive website.")
        task_id = res_submit["task_id"]

        # Pause
        res_pause = self.orchestrator.pause_task(task_id)
        self.assertEqual(res_pause["status"], TaskStatus.PAUSED.value)

        # Cancel
        res_cancel = self.orchestrator.cancel_task(task_id)
        self.assertEqual(res_cancel["status"], TaskStatus.CANCELLED.value)


if __name__ == "__main__":
    unittest.main()
