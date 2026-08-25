# MockBank Flowplane sandbox

A deterministic, stateful banking sandbox for demonstrating how Flowplane publishes and governs API operations as agent tools.

All identities, accounts, cards, transactions and notifications are synthetic. This is a demo sandbox, not a production banking system. It does not implement money movement or ledger semantics.

## Architecture

JSON Server `0.17.4` is the application framework and `db.json` is the local state store. `server.js` uses the supported programmatic extension points:

1. `jsonServer.create()`;
2. standard middleware and JSON body parsing;
3. health, validation and card-blocking middleware;
4. `jsonServer.router(DB_FILE)` mounted at `/v2/api`.

Ordinary CRUD, filtering and persistence remain JSON Server behavior. Custom mutations use `router.db`, so generated routes and middleware share one authoritative state store.

MockServer is separate. It is available only through the optional `fault-injection` Compose profile and is not the canonical backend.

## Demo scenario

A bounded agent:

1. finds synthetic customer `2`;
2. lists the customer's accounts and cards;
3. finds transaction `DEMO-SUSPICIOUS-0001` on account `4`;
4. blocks card `3` with reason `suspected_fraud`;
5. creates and reads back a customer notification.

The curated contract in `openapi.flowplane-demo.yaml` publishes seven operations rather than the broad API in `openapi.yaml`:

- `getCustomer`
- `listCustomerAccounts`
- `listAccountTransactions`
- `listCustomerCards`
- `blockCard`
- `createCustomerNotification`
- `listCustomerNotifications`

## Local sandbox

Requirements: Node.js 22+ and Python 3.9+.

```bash
npm ci
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
npm run reset
npm start
```

The service listens on `http://127.0.0.1:10097` by default:

```bash
curl http://127.0.0.1:10097/healthz
curl http://127.0.0.1:10097/readyz
curl http://127.0.0.1:10097/v2/api/customers/2
curl 'http://127.0.0.1:10097/v2/api/transactions?accountId=4'
```

`npm run reset` restores `db.json` byte-for-byte from `fixtures/seed.json`. Restart a running server after resetting because JSON Server keeps the loaded database in memory.

Override the local process settings with `HOST`, `PORT`, `DB_FILE`, `SEED_FILE` and `DEMO_NOW`.

## Tests

Run the complete suite with the Python virtual environment on `PATH`:

```bash
PATH="$PWD/.venv/bin:$PATH" npm test
npm audit
```

The suite validates the curated OpenAPI contract, JSON Server behavior, ownership-filter boundaries, state transitions, deterministic reset, traffic verification and the Flowplane MCP descriptor client.

## Container runtime

Docker Compose and Podman Compose are both supported:

```bash
docker compose up --build --wait sandbox
# or
podman compose up --build --wait sandbox
```

The container:

- runs as an unprivileged Node user;
- listens on container port `10097`;
- stores mutable state in the `mockbank-data` volume;
- initializes that volume from `fixtures/seed.json`;
- exposes `/readyz` as its health check.

Use `MOCKBANK_PORT` to change the host port. Optional scripted MockServer responses run separately:

```bash
docker compose --profile fault-injection up fault-injection
```

## Traffic verification

The generator defaults to the curated contract and read-only methods. It compares actual status codes with each generated case's expected status; an unexpected success is a failure.

```bash
.venv/bin/python traffic-generator.py --requests 30 --delay 0 --error-rate 0.4
.venv/bin/python traffic-generator.py --requests 20 --methods GET --verbose
```

Mutating traffic requires explicit permission:

```bash
.venv/bin/python traffic-generator.py \
  --allow-mutations --methods POST --paths cards notifications --requests 5
```

Do not pass real credentials through `--header`; command lines can be observable to other local processes.

## Flowplane `v3.1.3` end-to-end demo

Requirements:

- Docker or Podman with Compose;
- the published image `ghcr.io/rajeevramani/flowplane:3.1.3-eval`;
- Flowplane's released `compose.eval.yml` available locally.

By default, `scripts/demo.sh` expects a sibling checkout at `../flowplane/compose.eval.yml`. Otherwise set an explicit path:

```bash
export FLOWPLANE_COMPOSE_FILE=/absolute/path/to/compose.eval.yml
scripts/demo.sh all
```

`all` performs a clean, disposable verification:

1. builds and starts the stateful MockBank container;
2. starts the released Flowplane evaluator and Envoy;
3. connects both stacks through the `flowplane-demo` network;
4. exposes MockBank through a dedicated Envoy listener;
5. imports and publishes the seven-operation OpenAPI contract;
6. creates a `gateway-tool` agent granted only `mcp-tools:execute` on `default`;
7. executes the investigation and mutation journey through Flowplane-issued gateway descriptors;
8. attempts and verifies a denied invocation against `restricted`;
9. verifies tool count, default-team connection attribution, zero restricted-team attribution and xDS status;
10. removes both demo stacks, their volumes and temporary token files.

Sanitized run evidence is written under ignored `traffic-output/flowplane-demo/`. Agent and administrator tokens exist only in a mode-`0600` temporary directory and are removed during teardown.

The default host ports are:

| Service | Port |
| --- | ---: |
| MockBank | `10097` |
| Flowplane API/MCP | `18080` |
| Existing evaluator gateway | `11000` |
| MockBank gateway | `11001` |

Override them with `MOCKBANK_HOST_PORT`, `FLOWPLANE_API_PORT`, `FLOWPLANE_GATEWAY_PORT` and `FLOWPLANE_DEMO_GATEWAY_PORT`.

For an interactive run that leaves services up:

```bash
scripts/demo.sh up
scripts/demo.sh setup
scripts/demo.sh run
scripts/demo.sh status
scripts/demo.sh down
```

The MCP call returns a short-lived `gateway_invocation` descriptor. The demo client then executes that descriptor through Envoy. The distinction is deliberate: Flowplane publishes, authorizes and describes the governed invocation; the client performs the HTTP request.

## Limitations

- Synthetic data only.
- Stateful single-process JSON file storage.
- No production authentication inside MockBank; Flowplane is the demonstrated authorization boundary.
- No HA, durability, real ledger, debit/credit or transfer state machine.
- The evaluator path demonstrates local governance behavior; it is not a production deployment architecture.
