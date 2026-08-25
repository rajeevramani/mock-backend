#!/usr/bin/env python3
"""Minimal Flowplane MCP client for the MockBank demonstration."""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import urllib.error
import urllib.request
from typing import Any

TOOL_PREFIX = "api_mockbank-fraud-"
EXPECTED_TOOLS = {
    f"{TOOL_PREFIX}blockcard",
    f"{TOOL_PREFIX}createcustomernotification",
    f"{TOOL_PREFIX}getcustomer",
    f"{TOOL_PREFIX}listaccounttransactions",
    f"{TOOL_PREFIX}listcustomeraccounts",
    f"{TOOL_PREFIX}listcustomercards",
    f"{TOOL_PREFIX}listcustomernotifications",
}


def read_secret(path: str) -> str:
    return pathlib.Path(path).read_text().strip()


def write_secret(path: str, value: str) -> None:
    target = pathlib.Path(path)
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.write(descriptor, value.encode())
    finally:
        os.close(descriptor)


def json_request(
    url: str,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    body: Any = None,
) -> tuple[Any, Any]:
    request_headers = dict(headers or {})
    encoded = None
    if body is not None:
        encoded = json.dumps(body).encode()
        request_headers.setdefault("content-type", "application/json")
    request = urllib.request.Request(url, data=encoded, headers=request_headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            text = response.read().decode()
            return response, json.loads(text) if text else None
    except urllib.error.HTTPError as error:
        detail = error.read().decode(errors="replace")
        raise RuntimeError(f"HTTP {error.code} from {url}: {detail}") from error


class McpClient:
    def __init__(self, api_base: str, token: str):
        self.url = f"{api_base.rstrip('/')}/api/v1/mcp"
        self.token = token
        self.session: str | None = None
        self.next_id = 1

    def rpc(self, method: str, params: dict[str, Any], initialize: bool = False) -> dict[str, Any]:
        headers = {
            "authorization": f"Bearer {self.token}",
            "content-type": "application/json",
        }
        if self.session:
            headers["mcp-session-id"] = self.session
        response, payload = json_request(
            self.url,
            method="POST",
            headers=headers,
            body={"jsonrpc": "2.0", "id": self.next_id, "method": method, "params": params},
        )
        if not isinstance(payload, dict):
            raise RuntimeError(f"MCP endpoint returned a non-object response: {payload}")
        self.next_id += 1
        if initialize:
            self.session = response.headers.get("mcp-session-id")
            if not self.session:
                raise RuntimeError("Flowplane initialize response omitted mcp-session-id")
        return payload

    def initialize(self) -> None:
        payload = self.rpc("initialize", {"protocolVersion": "2025-11-25"}, initialize=True)
        if payload.get("result", {}).get("protocolVersion") != "2025-11-25":
            raise RuntimeError(f"unexpected MCP initialize response: {payload}")

    def tool_names(self, team: str) -> set[str]:
        payload = self.rpc("tools/list", {"team": team})
        if "error" in payload:
            raise RuntimeError(f"tools/list failed: {payload['error']}")
        return {tool["name"] for tool in payload["result"]["tools"]}

    def call(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        return self.rpc("tools/call", {"name": name, "arguments": arguments})


def extract_descriptor(response: dict[str, Any]) -> dict[str, Any]:
    result = response.get("result", {})
    if result.get("isError"):
        code = result.get("error", {}).get("code", "mcp_error")
        message = result.get("error", {}).get("message", "tool call failed")
        raise RuntimeError(f"{code}: {message}")
    descriptor = result.get("structuredContent")
    if not isinstance(descriptor, dict) or descriptor.get("type") != "gateway_invocation":
        raise RuntimeError(f"tool call did not return a gateway_invocation descriptor: {response}")
    return descriptor


def denial_code(response: dict[str, Any]) -> str | None:
    if response.get("error"):
        return response["error"].get("data", {}).get("code") or response["error"].get("code")
    result = response.get("result", {})
    if result.get("isError"):
        return result.get("error", {}).get("code")
    return None


def descriptor_request(descriptor: dict[str, Any]) -> urllib.request.Request:
    if descriptor.get("type") != "gateway_invocation":
        raise ValueError("descriptor type must be gateway_invocation")
    headers = {str(key): str(value) for key, value in descriptor.get("headers", {}).items()}
    body = descriptor.get("body")
    encoded = None if body is None else json.dumps(body).encode()
    if encoded is not None:
        headers.setdefault("content-type", "application/json")
    return urllib.request.Request(
        descriptor["url"],
        data=encoded,
        headers=headers,
        method=descriptor["method"],
    )


def execute_descriptor(descriptor: dict[str, Any]):
    request = descriptor_request(descriptor)
    with urllib.request.urlopen(request, timeout=30) as response:
        text = response.read().decode()
        return response.status, json.loads(text) if text else None


def assert_catalog(client: McpClient, team: str) -> None:
    found = {name for name in client.tool_names(team) if name.startswith(TOOL_PREFIX)}
    if found != EXPECTED_TOOLS:
        raise RuntimeError(f"unexpected MockBank tool catalog: {sorted(found)}")


def run_journey(args) -> None:
    client = McpClient(args.api_base, read_secret(args.token_file))
    client.initialize()
    assert_catalog(client, args.team)
    steps = [
        ("getcustomer", {"team": args.team, "pathParams": {"id": "2"}}),
        ("listcustomeraccounts", {"team": args.team, "query": {"customerId": 2}}),
        ("listaccounttransactions", {"team": args.team, "query": {"accountId": 4}}),
        ("listcustomercards", {"team": args.team, "query": {"customerId": 2}}),
        (
            "blockcard",
            {
                "team": args.team,
                "pathParams": {"id": "3"},
                "headers": {"content-type": "application/json"},
                "body": {"reason": "suspected_fraud"},
            },
        ),
        (
            "createcustomernotification",
            {
                "team": args.team,
                "headers": {"content-type": "application/json"},
                "body": {
                    "customerId": 2,
                    "type": "security",
                    "title": "Synthetic card blocked",
                    "message": "Your synthetic card ending 7756 was blocked after suspected fraud.",
                    "priority": "high",
                },
            },
        ),
        ("listcustomernotifications", {"team": args.team, "query": {"customerId": 2}}),
    ]
    results: dict[str, Any] = {}
    evidence = []
    for operation, arguments in steps:
        descriptor = extract_descriptor(client.call(f"{TOOL_PREFIX}{operation}", arguments))
        status, result = execute_descriptor(descriptor)
        if status >= 400:
            raise RuntimeError(f"gateway invocation failed for {operation}: HTTP {status}")
        results[operation] = result
        evidence.append(
            {
                "operationId": descriptor["operationId"],
                "correlationId": descriptor["correlationId"],
                "method": descriptor["method"],
                "url": descriptor["url"],
                "status": status,
            }
        )

    if results["getcustomer"].get("id") != 2:
        raise RuntimeError("customer investigation returned the wrong fixture")
    if [item["id"] for item in results["listcustomeraccounts"]] != [4, 5]:
        raise RuntimeError("account ownership result differs from the fixture")
    if not any(item.get("reference") == "DEMO-SUSPICIOUS-0001" for item in results["listaccounttransactions"]):
        raise RuntimeError("suspicious transaction was not found")
    if results["blockcard"].get("status") != "blocked":
        raise RuntimeError("card did not transition to blocked")
    notification_id = results["createcustomernotification"]["id"]
    if not any(item.get("id") == notification_id for item in results["listcustomernotifications"]):
        raise RuntimeError("created notification was not returned by readback")

    pathlib.Path(args.evidence).write_text(
        json.dumps({"steps": evidence, "blockedCardId": 3, "notificationId": notification_id}, indent=2) + "\n"
    )
    print(f"journey verified: {len(evidence)} gateway invocations, card blocked, notification persisted")


def create_agent(args) -> None:
    token = read_secret(args.admin_token_file)
    _, response = json_request(
        f"{args.api_base.rstrip('/')}/api/v1/agents",
        method="POST",
        headers={"authorization": f"Bearer {token}"},
        body={
            "name": args.name,
            "kind": "gateway-tool",
            "grants": [{"team_id": args.team_id, "resource": "mcp-tools", "action": "execute"}],
        },
    )
    if not isinstance(response, dict):
        raise RuntimeError(f"agent endpoint returned a non-object response: {response}")
    write_secret(args.agent_token_file, response["token"])
    print(f"bounded demo agent created: {response['agent']['id']}")


def run_denial(args) -> None:
    client = McpClient(args.api_base, read_secret(args.token_file))
    client.initialize()
    assert_catalog(client, args.allowed_team)
    response = client.call(
        f"{TOOL_PREFIX}getcustomer",
        {"team": args.denied_team, "pathParams": {"id": "2"}},
    )
    code = denial_code(response)
    if code != "forbidden":
        raise RuntimeError(f"cross-team invocation unexpectedly returned {code}: {response}")
    pathlib.Path(args.evidence).write_text(
        json.dumps({"allowedTeam": args.allowed_team, "deniedTeam": args.denied_team, "code": code}, indent=2) + "\n"
    )
    print(f"cross-team invocation denied: {code}")


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser()
    commands = root.add_subparsers(dest="command", required=True)

    journey = commands.add_parser("journey")
    journey.add_argument("--api-base", required=True)
    journey.add_argument("--token-file", required=True)
    journey.add_argument("--team", default="default")
    journey.add_argument("--evidence", required=True)
    journey.set_defaults(handler=run_journey)

    agent = commands.add_parser("create-agent")
    agent.add_argument("--api-base", required=True)
    agent.add_argument("--admin-token-file", required=True)
    agent.add_argument("--agent-token-file", required=True)
    agent.add_argument("--team-id", required=True)
    agent.add_argument("--name", default="mockbank-demo-agent")
    agent.set_defaults(handler=create_agent)

    denial = commands.add_parser("deny")
    denial.add_argument("--api-base", required=True)
    denial.add_argument("--token-file", required=True)
    denial.add_argument("--allowed-team", default="default")
    denial.add_argument("--denied-team", required=True)
    denial.add_argument("--evidence", required=True)
    denial.set_defaults(handler=run_denial)
    return root


def main() -> None:
    args = parser().parse_args()
    args.handler(args)


if __name__ == "__main__":
    main()
