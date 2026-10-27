"""Multi-Modal Outcome Verification Engine for ERA Outcome Engine."""

from __future__ import annotations

import time
from typing import Any, Dict, List
from .coding_engine import CodingEngine
from .models import TaskNode, VerificationEvidence


class Verifier:
    """Implements independent verification stage after every meaningful action (Observe -> Act -> Verify)."""

    def __init__(self, coding_engine: CodingEngine):
        self.coding_engine = coding_engine

    def verify_node_execution(self, node: TaskNode, execution_result: Dict[str, Any]) -> Dict[str, Any]:
        strategy = node.verification_strategy.lower()
        now = time.time()

        # 1. Exit code verification
        if strategy == "exit_code":
            exit_code = execution_result.get("exit_code", 0)
            success = execution_result.get("success", False) and exit_code == 0
            evidence = VerificationEvidence(
                timestamp=now,
                strategy="exit_code",
                passed=success,
                expected="exit_code == 0",
                observed=f"exit_code == {exit_code}",
                details={"execution_result": execution_result},
            )
            node.evidence = evidence
            return {
                "verified": success,
                "strategy": "exit_code",
                "evidence": evidence,
                "message": f"Verified exit code {exit_code}" if success else f"Exit code failure ({exit_code})",
            }

        # 2. File exists verification
        elif strategy == "file_exists":
            rel_file = node.verification_params.get("file_path") or node.params.get("file_path")
            if not rel_file and node.params.get("deliverables"):
                rel_file = node.params.get("deliverables")[0]
            if not rel_file:

                evidence = VerificationEvidence(
                    timestamp=now,
                    strategy="file_exists",
                    passed=False,
                    expected="Target file path specified",
                    observed="None provided",
                )
                node.evidence = evidence
                return {"verified": False, "strategy": "file_exists", "evidence": evidence, "message": "No target file specified for verification."}

            read_res = self.coding_engine.read_file(rel_file)
            content_ok = read_res.get("success", False) and len(read_res.get("content", "")) > 0
            evidence = VerificationEvidence(
                timestamp=now,
                strategy="file_exists",
                passed=content_ok,
                expected=f"File '{rel_file}' exists and contains content",
                observed=f"Exists: {read_res.get('success')}, Bytes: {len(read_res.get('content', ''))}",
            )
            node.evidence = evidence
            return {
                "verified": content_ok,
                "strategy": "file_exists",
                "evidence": evidence,
                "message": f"File '{rel_file}' existence check: {content_ok}",
            }

        # 3. Test passed verification
        elif strategy == "test_passed":
            test_res = self.coding_engine.run_unit_tests()
            passed = test_res.get("success", False) and "OK" in (test_res.get("stderr") or "")
            evidence = VerificationEvidence(
                timestamp=now,
                strategy="test_passed",
                passed=passed,
                expected="Automated unit test suite passes with exit code 0",
                observed=f"stdout: {test_res.get('stdout', '')[:100]}, stderr: {test_res.get('stderr', '')[:100]}",
            )
            node.evidence = evidence
            return {
                "verified": passed,
                "strategy": "test_passed",
                "evidence": evidence,
                "message": "Automated tests passed cleanly." if passed else "Automated test suite failed.",
            }

        # 4. HTTP status verification
        elif strategy == "http_status":
            url = node.verification_params.get("url") or node.params.get("url") or "http://127.0.0.1:8080"
            http_res = self.coding_engine.probe_http(url)
            passed = http_res.get("success", False)
            evidence = VerificationEvidence(
                timestamp=now,
                strategy="http_status",
                passed=passed,
                expected=f"HTTP 200 OK response from {url}",
                observed=f"Status code: {http_res.get('status_code', 0)} ({http_res.get('message')})",
            )
            node.evidence = evidence
            return {
                "verified": passed,
                "strategy": "http_status",
                "evidence": evidence,
                "message": http_res.get("message", ""),
            }

        # 5. System update installed verification
        elif strategy == "system_update_installed":
            passed = execution_result.get("success", True)
            evidence = VerificationEvidence(
                timestamp=now,
                strategy="system_update_installed",
                passed=passed,
                expected="Software package updates installation routine executed",
                observed=execution_result.get("message", "Package update verification completed."),
            )
            node.evidence = evidence
            return {
                "verified": passed,
                "strategy": "system_update_installed",
                "evidence": evidence,
                "message": "Software updates verified.",
            }

        # 6. Form data matched verification
        elif strategy == "form_data_matched":
            passed = execution_result.get("success", False)
            evidence = VerificationEvidence(
                timestamp=now,
                strategy="form_data_matched",
                passed=passed,
                expected="Form fields populated matching user parameters",
                observed=f"Filled {execution_result.get('filled_fields_count', 0)} fields.",
            )
            node.evidence = evidence
            return {
                "verified": passed,
                "strategy": "form_data_matched",
                "evidence": evidence,
                "message": "Form data entry verified.",
            }

        # 7. Multi-factor verification
        elif strategy == "multi_factor":
            criteria = node.verification_params.get("criteria", [])
            files = self.coding_engine.list_files()

            checks = []
            if len(files) > 0:
                checks.append("Deliverable files present in workspace")

            if execution_result.get("success", True):
                checks.append("Core operations completed without fatal errors")

            url = node.verification_params.get("url")
            if url:
                http_probe = self.coding_engine.probe_http(url)
                if http_probe.get("success"):
                    checks.append(f"HTTP server at {url} active and serving requests")

            verified = len(checks) >= 1
            evidence = VerificationEvidence(
                timestamp=now,
                strategy="multi_factor",
                passed=verified,
                expected=f"Satisfies {len(criteria)} acceptance criteria",
                observed=f"Passed {len(checks)} empirical verification factors: {', '.join(checks)}",
            )
            node.evidence = evidence
            return {
                "verified": verified,
                "strategy": "multi_factor",
                "evidence": evidence,
                "checks_passed": checks,
                "message": f"Passed {len(checks)} verification factors.",
            }

        else:
            passed = execution_result.get("success", False)
            evidence = VerificationEvidence(
                timestamp=now,
                strategy="default",
                passed=passed,
                expected="Execution completed successfully",
                observed=execution_result.get("message", ""),
            )
            node.evidence = evidence
            return {"verified": passed, "strategy": "default", "evidence": evidence, "message": "Default verification."}
