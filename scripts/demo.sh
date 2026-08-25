#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
FLOWPLANE_COMPOSE_FILE=${FLOWPLANE_COMPOSE_FILE:-"$ROOT/../flowplane/compose.eval.yml"}
FLOWPLANE_IMAGE=${FLOWPLANE_IMAGE:-ghcr.io/rajeevramani/flowplane:3.1.3-eval}
FLOWPLANE_API_PORT=${FLOWPLANE_API_PORT:-18080}
FLOWPLANE_GATEWAY_PORT=${FLOWPLANE_GATEWAY_PORT:-11000}
FLOWPLANE_DEMO_GATEWAY_PORT=${FLOWPLANE_DEMO_GATEWAY_PORT:-11001}
MOCKBANK_HOST_PORT=${MOCKBANK_HOST_PORT:-10097}
STATE_DIR=${STATE_DIR:-${TMPDIR:-/tmp}/mockbank-flowplane-demo-state}
EVIDENCE_DIR=${EVIDENCE_DIR:-$ROOT/traffic-output/flowplane-demo}
MOCKBANK_PROJECT=mockbank-demo
FLOWPLANE_PROJECT=flowplane-mockbank-demo

if command -v docker >/dev/null 2>&1; then
  CONTAINER_RUNTIME=docker
elif command -v podman >/dev/null 2>&1; then
  CONTAINER_RUNTIME=podman
else
  echo "Docker or Podman with Compose support is required" >&2
  exit 1
fi

COMPOSE=("$CONTAINER_RUNTIME" compose)
MOCKBANK_FILES=(-f "$ROOT/docker-compose.yml" -f "$ROOT/compose.flowplane-demo.yml")
FLOWPLANE_FILES=(-f "$FLOWPLANE_COMPOSE_FILE" -f "$ROOT/compose.flowplane-eval.override.yml")

require_flowplane_compose() {
  if [[ ! -f "$FLOWPLANE_COMPOSE_FILE" ]]; then
    echo "Flowplane evaluator Compose file not found: $FLOWPLANE_COMPOSE_FILE" >&2
    echo "Set FLOWPLANE_COMPOSE_FILE to the v3.1.3 compose.eval.yml path." >&2
    exit 1
  fi
}

fp_compose() {
  FLOWPLANE_EVAL_IMAGE="$FLOWPLANE_IMAGE" \
  FLOWPLANE_EVAL_API_PORT="$FLOWPLANE_API_PORT" \
  FLOWPLANE_EVAL_GATEWAY_PORT="$FLOWPLANE_GATEWAY_PORT" \
  FLOWPLANE_DEMO_GATEWAY_PORT="$FLOWPLANE_DEMO_GATEWAY_PORT" \
    "${COMPOSE[@]}" -p "$FLOWPLANE_PROJECT" "${FLOWPLANE_FILES[@]}" "$@"
}

fp_cli() {
  local command='FLOWPLANE_TOKEN=$(cat /shared/dev-token) FLOWPLANE_ORG=dev-org FLOWPLANE_TEAM=default flowplane'
  local argument quoted
  for argument in "$@"; do
    printf -v quoted '%q' "$argument"
    command+=" $quoted"
  done
  fp_compose exec -T flowplane-eval sh -c "$command"
}

json_value() {
  local file=$1
  local expression=$2
  python3 - "$file" "$expression" <<'PY'
import json
import sys
value = json.load(open(sys.argv[1]))
for part in sys.argv[2].split('.'):
    value = value[int(part)] if isinstance(value, list) else value[part]
print(value)
PY
}

up() {
  require_flowplane_compose
  mkdir -p "$STATE_DIR"
  chmod 700 "$STATE_DIR"
  if ! "$CONTAINER_RUNTIME" network inspect flowplane-demo >/dev/null 2>&1; then
    "$CONTAINER_RUNTIME" network create flowplane-demo >/dev/null
    touch "$STATE_DIR/network-created"
  fi

  MOCKBANK_PORT="$MOCKBANK_HOST_PORT" \
    "${COMPOSE[@]}" -p "$MOCKBANK_PROJECT" "${MOCKBANK_FILES[@]}" \
    up -d --build --wait sandbox

  fp_compose up -d --no-build --wait flowplane-eval envoy flowplane-agent

  curl --fail --silent --show-error --retry 20 --retry-delay 1 --retry-all-errors \
    "http://127.0.0.1:$MOCKBANK_HOST_PORT/readyz" >/dev/null
  curl --fail --silent --show-error --retry 20 --retry-delay 1 --retry-all-errors \
    "http://127.0.0.1:$FLOWPLANE_API_PORT/healthz" >/dev/null
  echo "stacks ready: MockBank $MOCKBANK_HOST_PORT, Flowplane $FLOWPLANE_API_PORT"
}

setup() {
  mkdir -p "$STATE_DIR" "$EVIDENCE_DIR"
  chmod 700 "$STATE_DIR"

  fp_compose exec -T flowplane-eval cat /shared/dev-token >"$STATE_DIR/admin-token"
  chmod 600 "$STATE_DIR/admin-token"
  fp_compose cp "$ROOT/openapi.flowplane-demo.yaml" \
    flowplane-eval:/tmp/openapi.flowplane-demo.yaml

  fp_cli expose http://mockbank:10097 \
    --name mockbank --path / --port 10001 \
    --public-base-url "http://127.0.0.1:$FLOWPLANE_DEMO_GATEWAY_PORT" \
    --output json >"$STATE_DIR/expose.json"

  local route_id listener_id
  route_id=$(json_value "$STATE_DIR/expose.json" data.route_config.id)
  listener_id=$(json_value "$STATE_DIR/expose.json" data.listener.id)

  fp_cli api create mockbank-fraud \
    --from-openapi /tmp/openapi.flowplane-demo.yaml \
    --team default --route-config-id "$route_id" --listener-id "$listener_id" \
    --virtual-host default --route all --output json >"$STATE_DIR/api-create.json"
  fp_cli api spec publish mockbank-fraud 1 --team default \
    --reason "Flowplane demo contract reviewed" --output json >"$EVIDENCE_DIR/publish.json"

  fp_cli team create restricted --display-name "Restricted Demo Team" \
    --output json >"$STATE_DIR/restricted-team.json"
  fp_cli team list --output json >"$STATE_DIR/teams.json"

  local default_team_id
  default_team_id=$(python3 - "$STATE_DIR/teams.json" <<'PY'
import json
import sys
teams = json.load(open(sys.argv[1]))["data"]
print(next(team["id"] for team in teams if team["name"] == "default"))
PY
)
  python3 "$ROOT/scripts/flowplane_mcp.py" create-agent \
    --api-base "http://127.0.0.1:$FLOWPLANE_API_PORT" \
    --admin-token-file "$STATE_DIR/admin-token" \
    --agent-token-file "$STATE_DIR/agent-token" \
    --team-id "$default_team_id"
  echo "Flowplane API published and bounded agent created"
}

run_journey() {
  python3 "$ROOT/scripts/flowplane_mcp.py" journey \
    --api-base "http://127.0.0.1:$FLOWPLANE_API_PORT" \
    --token-file "$STATE_DIR/agent-token" --team default \
    --evidence "$EVIDENCE_DIR/journey.json"
  python3 "$ROOT/scripts/flowplane_mcp.py" deny \
    --api-base "http://127.0.0.1:$FLOWPLANE_API_PORT" \
    --token-file "$STATE_DIR/agent-token" \
    --allowed-team default --denied-team restricted \
    --evidence "$EVIDENCE_DIR/denial.json"
}

collect_status() {
  fp_cli mcp status --team default --output json >"$EVIDENCE_DIR/mcp-status.json"
  fp_cli mcp connections --team default --output json >"$STATE_DIR/default-connections.json"
  fp_cli mcp connections --team restricted --output json >"$STATE_DIR/restricted-connections.json"
  fp_cli ops xds status --team default --output json >"$EVIDENCE_DIR/xds-status.json"
  python3 - "$EVIDENCE_DIR/mcp-status.json" "$STATE_DIR/default-connections.json" \
    "$STATE_DIR/restricted-connections.json" "$EVIDENCE_DIR/governance.json" <<'PY'
import json
import sys
status = json.load(open(sys.argv[1]))["data"]
default = json.load(open(sys.argv[2]))["data"]
restricted = json.load(open(sys.argv[3]))["data"]
assert status["dynamic_enabled_tool_count"] == 7, status
assert len(default) >= 1, default
assert len(restricted) == 0, restricted
summary = {
    "dynamicEnabledToolCount": status["dynamic_enabled_tool_count"],
    "defaultTeamConnectionCount": len(default),
    "restrictedTeamConnectionCount": len(restricted),
    "crossTenantAttributionPrevented": True,
}
open(sys.argv[4], "w").write(json.dumps(summary, indent=2) + "\n")
print("governance verified: 7 tools, default attribution present, restricted attribution absent")
PY
}

down() {
  local remove_network=false
  [[ -f "$STATE_DIR/network-created" ]] && remove_network=true
  if [[ -f "$FLOWPLANE_COMPOSE_FILE" ]]; then
    fp_compose down -v --remove-orphans
  fi
  MOCKBANK_PORT="$MOCKBANK_HOST_PORT" \
    "${COMPOSE[@]}" -p "$MOCKBANK_PROJECT" "${MOCKBANK_FILES[@]}" \
    down -v --remove-orphans
  if [[ "$remove_network" == true ]]; then
    "$CONTAINER_RUNTIME" network rm flowplane-demo >/dev/null
  fi
  rm -f \
    "$STATE_DIR/admin-token" "$STATE_DIR/agent-token" \
    "$STATE_DIR/expose.json" "$STATE_DIR/api-create.json" \
    "$STATE_DIR/restricted-team.json" "$STATE_DIR/teams.json" \
    "$STATE_DIR/default-connections.json" "$STATE_DIR/restricted-connections.json" \
    "$STATE_DIR/network-created"
  rmdir "$STATE_DIR" 2>/dev/null || true
  echo "demo stacks and secret state removed"
}

all() {
  down >/dev/null 2>&1 || true
  trap 'down >/dev/null 2>&1 || true' EXIT
  up
  setup
  run_journey
  collect_status
  echo "end-to-end demo verified; sanitized evidence: $EVIDENCE_DIR"
}

case ${1:-} in
  up) up ;;
  setup) setup ;;
  run) run_journey ;;
  status) collect_status ;;
  down) down ;;
  all) all ;;
  *)
    echo "Usage: scripts/demo.sh {up|setup|run|status|down|all}" >&2
    exit 2
    ;;
esac
