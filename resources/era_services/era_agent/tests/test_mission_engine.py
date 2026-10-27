"""Automated Test Suite for ERA Mission Engine, Tool Registry, Communication Router, Gmail & WhatsApp Real Adapters, Verification & Recovery.

Uses Python standard unittest library for 100% native execution compatibility.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from api_server import app
from era_agent.communication.gmail_adapter import GmailAdapter
from era_agent.communication.router import CommunicationRouter, comm_router
from era_agent.communication.whatsapp_adapter import WhatsAppAdapter
from era_agent.mission_engine.engine import ERAMissionEngine, MissionPlanner
from era_agent.mission_engine.models import Mission, MissionState, MissionStep, RiskLevel, StepStatus
from era_agent.tools.tool_registry import ERAToolRegistry, tool_registry


class TestMissionModelsAndPlanner(unittest.TestCase):
    def test_mission_initialization(self):
        mission = Mission(goal="Prepare my presentation")
        self.assertTrue(mission.id.startswith("mission_"))
        self.assertEqual(mission.state, MissionState.CREATED)
        self.assertEqual(mission.goal, "Prepare my presentation")
        self.assertEqual(len(mission.steps), 0)

    def test_planner_creates_presentation_steps(self):
        steps = MissionPlanner.plan_goal("prepare my presentation")
        self.assertGreaterEqual(len(steps), 2)
        actions = [s.action for s in steps]
        self.assertIn("create_file", actions)
        self.assertIn("read_file", actions)

    def test_planner_creates_communication_steps(self):
        steps = MissionPlanner.plan_goal("check gmail and whatsapp")
        actions = [s.action for s in steps]
        self.assertIn("gmail_list", actions)
        self.assertIn("whatsapp_list", actions)


class TestToolRegistryAndSafety(unittest.TestCase):
    def test_tool_registration_and_list(self):
        tools = tool_registry.list_tools()
        self.assertIn("open_app", tools)
        self.assertIn("create_file", tools)
        self.assertIn("shutdown", tools)
        self.assertIn("gmail_reply", tools)

    def test_permission_level_and_confirmation(self):
        self.assertTrue(tool_registry.requires_confirmation("shutdown", {}))
        self.assertFalse(tool_registry.requires_confirmation("read_file", {}))
        self.assertTrue(tool_registry.requires_confirmation("gmail_send", {}))
        self.assertTrue(tool_registry.requires_confirmation("whatsapp_send", {}))

    def test_file_create_and_read_execution(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test_mission.txt"
            registry = ERAToolRegistry()

            create_res = registry.execute("create_file", {"path": str(test_file), "content": "ERA Mission Active"})
            self.assertTrue(create_res["success"])

            verify_res = registry.verify("create_file", create_res, {"path": str(test_file)})
            self.assertTrue(verify_res["verified"])

            read_res = registry.execute("read_file", {"path": str(test_file)})
            self.assertTrue(read_res["success"])
            self.assertEqual(read_res["content"], "ERA Mission Active")


class TestGmailAdapterRealAndMock(unittest.TestCase):
    def test_gmail_mock_fallback_status(self):
        gmail = GmailAdapter(mock_mode=True)
        status = gmail.get_status()
        self.assertEqual(status["status"], "MOCK_MODE")

        res = gmail.list_emails(max_results=5)
        self.assertTrue(res["success"])
        self.assertGreater(res["count"], 0)
        self.assertIn("emails", res)

    def test_gmail_disconnected_real_status(self):
        gmail = GmailAdapter(credentials_path="nonexistent_creds.json", token_path="nonexistent_token.json", mock_mode=False)
        status = gmail.get_status()
        self.assertEqual(status["status"], "DISCONNECTED")

        res = gmail.list_emails()
        self.assertFalse(res["success"])
        self.assertEqual(res["message"], "Gmail is not connected yet.")

    def test_gmail_draft_and_send_with_verification(self):
        gmail = GmailAdapter(mock_mode=True)
        draft_res = gmail.create_draft("test@example.com", "Test Subject", "Test Body")
        self.assertTrue(draft_res["success"])
        self.assertIn("draft_id", draft_res)

        send_res = gmail.send_email("test@example.com", "Test Subject", "Test Body", draft_id=draft_res["draft_id"])
        self.assertTrue(send_res["success"])
        self.assertTrue(send_res["verified"])

        verify_res = gmail.verify_send(send_res["message_id"])
        self.assertTrue(verify_res["verified"])

    def test_gmail_reply_creation(self):
        gmail = GmailAdapter(mock_mode=True)
        reply_res = gmail.create_reply("msg_001", "Thanks for the update!")
        self.assertTrue(reply_res["success"])
        self.assertIn("draft_id", reply_res)


class TestWhatsAppAdapterRealAndMock(unittest.TestCase):
    def test_whatsapp_mock_and_auth_status(self):
        wa_mock = WhatsAppAdapter(mock_mode=True)
        self.assertEqual(wa_mock.get_status()["status"], "MOCK_MODE")

        wa_real = WhatsAppAdapter(api_token="test_token", phone_number_id="123456789", mock_mode=False)
        self.assertEqual(wa_real.get_status()["status"], "CONNECTED")

        wa_unauth = WhatsAppAdapter(api_token="", phone_number_id="", mock_mode=False)
        self.assertEqual(wa_unauth.get_status()["status"], "AUTH_REQUIRED")
        res = wa_unauth.list_messages()
        self.assertFalse(res["success"])
        self.assertIn("not connected", res["message"])

    def test_whatsapp_webhook_event_processing(self):
        wa = WhatsAppAdapter(api_token="token", phone_number_id="12345", mock_mode=False)
        sample_webhook = {
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "contacts": [{"wa_id": "+919876543210", "profile": {"name": "Rahul"}}],
                                "messages": [{"id": "wamid_in_01", "from": "+919876543210", "text": {"body": "Meeting at 5 PM"}, "timestamp": "1700000000"}],
                            }
                        }
                    ]
                }
            ]
        }
        res = wa.receive_webhook_event(sample_webhook)
        self.assertTrue(res["success"])
        self.assertEqual(res["processed"], 1)

        list_res = wa.list_messages()
        self.assertTrue(list_res["success"])
        self.assertEqual(list_res["count"], 1)
        self.assertEqual(list_res["messages"][0]["sender"], "Rahul")


class TestCommunicationRouter(unittest.TestCase):
    def test_router_read_and_send(self):
        router = CommunicationRouter()
        router.gmail.mock_mode = True
        router.whatsapp.mock_mode = True

        gmail_read = router.read("gmail")
        self.assertTrue(gmail_read["success"])

        wa_read = router.read("whatsapp")
        self.assertTrue(wa_read["success"])

        send_res = router.send("whatsapp", recipient="Rahul", message="Meeting confirmed")
        self.assertTrue(send_res["success"])


class TestMissionEngineLoop(unittest.TestCase):
    def test_full_mission_execution(self):
        engine = ERAMissionEngine()
        engine.tool_registry.tools["gmail_list"].execution_handler = lambda max_results=10: {"success": True, "emails": []}
        engine.tool_registry.tools["whatsapp_list"].execution_handler = lambda limit=10: {"success": True, "messages": []}

        mission = engine.create_mission(goal="prepare my presentation")
        completed_mission = engine.run(mission)
        self.assertIn(completed_mission.state, [MissionState.COMPLETED, MissionState.EXECUTING])
        self.assertGreater(completed_mission.to_dict()["progress_percent"], 0)


class TestAPIEndpoints(unittest.TestCase):
    def test_status_endpoint(self):
        client = TestClient(app)
        res = client.get("/status")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "online")
        self.assertIn("communication", data)

    def test_create_and_get_mission_endpoint(self):
        import base64, hashlib, hmac, json as _json, os, time
        agent_key = os.getenv("ERA_AGENT_API_KEY", "test-agent-key-for-boundary-tests")
        now = time.time()
        payload = {"device_id": "test", "status": "ACTIVE", "lease_expires_at": 0.0,
                   "issued_at": now, "expires_at": now + 30, "nonce": "testmission"}
        payload_b64 = base64.urlsafe_b64encode(
            _json.dumps(payload, separators=(",", ":")).encode()).decode("ascii")
        sig = hmac.new(agent_key.encode(), payload_b64.encode("ascii"), hashlib.sha256).hexdigest()
        headers = {"X-Era-Agent-Key": agent_key, "X-Era-Auth-Token": f"{payload_b64}.{sig}"}

        client = TestClient(app)
        res = client.post("/api/missions", json={"goal": "prepare my presentation"}, headers=headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("id", data)
        self.assertEqual(data["goal"], "prepare my presentation")

        mission_id = data["id"]
        get_res = client.get(f"/api/missions/{mission_id}")
        self.assertEqual(get_res.status_code, 200)
        self.assertEqual(get_res.json()["id"], mission_id)

    def test_gmail_and_whatsapp_status_endpoints(self):
        client = TestClient(app)
        res_g = client.get("/api/gmail/status")
        self.assertEqual(res_g.status_code, 200)

        res_w = client.get("/api/whatsapp/status")
        self.assertEqual(res_w.status_code, 200)


if __name__ == "__main__":
    unittest.main()
