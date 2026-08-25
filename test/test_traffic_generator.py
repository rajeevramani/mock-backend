import importlib.util
import pathlib
import sys
import unittest
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("traffic_generator", ROOT / "traffic-generator.py")
assert SPEC is not None
assert SPEC.loader is not None
traffic_generator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(traffic_generator)


class FakeElapsed:
    def total_seconds(self):
        return 0.01


class FakeResponse:
    def __init__(self, status_code):
        self.status_code = status_code
        self.elapsed = FakeElapsed()
        self.text = "{}"

    def json(self):
        return {}


class TrafficGeneratorStatusTest(unittest.TestCase):
    def make_bad_request(self, actual_status, expected_status):
        case = {
            "method": "GET",
            "path": "/v2/api/customers/999",
            "body": None,
            "headers": {"Content-Type": "application/json"},
            "expected_status": expected_status,
        }
        with patch.object(traffic_generator.requests, "request", return_value=FakeResponse(actual_status)):
            return traffic_generator.make_request(
                "http://localhost:10097",
                {"path": case["path"], "method": case["method"]},
                {},
                bad_request=case,
            )

    def test_expected_negative_status_is_a_passed_verification(self):
        result = self.make_bad_request(actual_status=404, expected_status=404)
        self.assertTrue(result["success"])
        self.assertTrue(result["negative_case"])
        self.assertEqual(result["expected_status"], 404)

    def test_unexpected_status_is_a_failed_verification(self):
        result = self.make_bad_request(actual_status=200, expected_status=404)
        self.assertFalse(result["success"])
        self.assertEqual(result["expected_status"], 404)
        self.assertEqual(result["status_code"], 200)

    def test_normal_request_still_uses_http_success_semantics(self):
        with patch.object(traffic_generator.requests, "request", return_value=FakeResponse(200)):
            result = traffic_generator.make_request(
                "http://localhost:10097",
                {"path": "/healthz", "method": "GET"},
                {},
            )
        self.assertTrue(result["success"])
        self.assertFalse(result["negative_case"])

    def test_curated_parameters_and_bodies_use_the_stable_demo_fixture(self):
        spec = traffic_generator.load_openapi_spec(str(ROOT / "openapi.flowplane-demo.yaml"))
        account_query = traffic_generator.generate_query_params("/v2/api/transactions", spec)
        customer_query = traffic_generator.generate_query_params("/v2/api/accounts", spec)
        self.assertEqual(account_query, {"accountId": 4})
        self.assertEqual(customer_query, {"customerId": 2})
        self.assertEqual(
            traffic_generator.generate_request_body("/v2/api/cards/{id}/block", "POST"),
            {"reason": "suspected_fraud"},
        )
        notification = traffic_generator.generate_request_body("/v2/api/notifications", "POST")
        self.assertEqual(notification["customerId"], 2)
        self.assertEqual(notification["type"], "security")

    def test_mutating_operations_require_explicit_opt_in(self):
        spec = traffic_generator.load_openapi_spec(str(ROOT / "openapi.flowplane-demo.yaml"))
        endpoints = traffic_generator.get_available_endpoints(spec)
        safe = traffic_generator.filter_endpoints(endpoints, allow_mutations=False)
        allowed = traffic_generator.filter_endpoints(endpoints, allow_mutations=True)
        self.assertTrue(all(item["method"] == "GET" for item in safe))
        self.assertTrue(any(item["method"] == "POST" for item in allowed))


if __name__ == "__main__":
    unittest.main()
