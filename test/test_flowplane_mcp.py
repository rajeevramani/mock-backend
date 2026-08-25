import json
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import flowplane_mcp


class DescriptorHelpersTest(unittest.TestCase):
    def test_descriptor_request_preserves_gateway_method_headers_and_json_body(self):
        descriptor = {
            "type": "gateway_invocation",
            "method": "POST",
            "url": "http://127.0.0.1:11001/v2/api/cards/3/block",
            "headers": {"host": "default", "content-type": "application/json"},
            "body": {"reason": "suspected_fraud"},
        }
        request = flowplane_mcp.descriptor_request(descriptor)
        self.assertEqual(request.method, "POST")
        self.assertEqual(request.full_url, descriptor["url"])
        self.assertEqual(json.loads(request.data), descriptor["body"])
        self.assertEqual(request.headers["Host"], "default")

    def test_descriptor_extraction_rejects_mcp_error_results(self):
        response = {
            "result": {
                "isError": True,
                "error": {"code": "forbidden"},
                "content": [{"type": "text", "text": "denied"}],
            }
        }
        with self.assertRaisesRegex(RuntimeError, "forbidden"):
            flowplane_mcp.extract_descriptor(response)

    def test_denial_code_supports_flowplane_result_error_shape(self):
        response = {"result": {"isError": True, "error": {"code": "forbidden"}}}
        self.assertEqual(flowplane_mcp.denial_code(response), "forbidden")


if __name__ == "__main__":
    unittest.main()
