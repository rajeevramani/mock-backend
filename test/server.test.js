'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const net = require('node:net');
const os = require('node:os');
const path = require('node:path');
const { spawn, spawnSync } = require('node:child_process');
const { after, before, test } = require('node:test');

const ROOT = path.resolve(__dirname, '..');
const SEED_FILE = path.join(ROOT, 'fixtures', 'seed.json');
let tempDir;
let dbFile;
let port;
let child;
let baseUrl;

async function unusedPort() {
  return new Promise((resolve, reject) => {
    const server = net.createServer();
    server.unref();
    server.on('error', reject);
    server.listen(0, '127.0.0.1', () => {
      const selected = server.address().port;
      server.close(() => resolve(selected));
    });
  });
}

async function waitForHealth(url, process, timeoutMs = 5000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (process.exitCode !== null) {
      throw new Error(`server exited before becoming healthy (${process.exitCode})`);
    }
    try {
      const response = await fetch(`${url}/healthz`);
      if (response.ok) return;
    } catch (_) {
      // Retry until the deadline while the child process starts.
    }
    await new Promise((resolve) => setTimeout(resolve, 50));
  }
  throw new Error('server did not become healthy before timeout');
}

async function request(method, pathname, body) {
  const response = await fetch(`${baseUrl}${pathname}`, {
    method,
    headers: body === undefined ? {} : { 'content-type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const text = await response.text();
  return {
    status: response.status,
    body: text ? JSON.parse(text) : null,
  };
}

before(async () => {
  tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'mockbank-test-'));
  dbFile = path.join(tempDir, 'db.json');
  fs.copyFileSync(SEED_FILE, dbFile);
  port = await unusedPort();
  baseUrl = `http://127.0.0.1:${port}`;
  child = spawn(process.execPath, ['server.js'], {
    cwd: ROOT,
    env: {
      ...process.env,
      DB_FILE: dbFile,
      SEED_FILE,
      HOST: '127.0.0.1',
      PORT: String(port),
      DEMO_NOW: '2026-08-25T00:00:00.000Z',
    },
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  await waitForHealth(baseUrl, child);
});

after(async () => {
  if (child && child.exitCode === null) {
    child.kill('SIGTERM');
    await new Promise((resolve) => child.once('exit', resolve));
  }
  if (tempDir) fs.rmSync(tempDir, { recursive: true, force: true });
});

test('health and readiness endpoints identify the JSON Server sandbox', async () => {
  const health = await request('GET', '/healthz');
  assert.equal(health.status, 200);
  assert.deepEqual(health.body, { status: 'ok', service: 'mockbank-banking-sandbox' });

  const ready = await request('GET', '/readyz');
  assert.equal(ready.status, 200);
  assert.equal(ready.body.status, 'ready');
  assert.equal(ready.body.database, 'available');
});

test('JSON Server reads and filters the deterministic investigation fixture', async () => {
  const customer = await request('GET', '/v2/api/customers/2');
  assert.equal(customer.status, 200);
  assert.equal(customer.body.firstName, 'Sarah');

  const accounts = await request('GET', '/v2/api/accounts?customerId=2');
  assert.equal(accounts.status, 200);
  assert.deepEqual(accounts.body.map((account) => account.id), [4, 5]);

  const transactions = await request('GET', '/v2/api/transactions?accountId=4');
  assert.equal(transactions.status, 200);
  assert.ok(transactions.body.some((item) => item.reference === 'DEMO-SUSPICIOUS-0001'));

  const cards = await request('GET', '/v2/api/cards?customerId=2');
  assert.equal(cards.status, 200);
  assert.deepEqual(cards.body.map((card) => card.id), [3, 4]);
});

test('agent-facing list routes require valid ownership filters', async () => {
  for (const route of ['accounts', 'cards', 'notifications']) {
    const missing = await request('GET', `/v2/api/${route}`);
    assert.equal(missing.status, 400, route);
    assert.equal(missing.body.error, 'customer_id_required', route);

    const unknown = await request('GET', `/v2/api/${route}?customerId=999`);
    assert.equal(unknown.status, 404, route);
    assert.equal(unknown.body.error, 'customer_not_found', route);
  }

  const missingAccount = await request('GET', '/v2/api/transactions');
  assert.equal(missingAccount.status, 400);
  assert.equal(missingAccount.body.error, 'account_id_required');

  const unknownAccount = await request('GET', '/v2/api/transactions?accountId=999');
  assert.equal(unknownAccount.status, 404);
  assert.equal(unknownAccount.body.error, 'account_not_found');
});

test('blocking a card validates input and persists an idempotent state transition', async () => {
  const invalid = await request('POST', '/v2/api/cards/3/block', { reason: 'anything' });
  assert.equal(invalid.status, 400);
  assert.match(invalid.body.error, /reason/i);

  const blocked = await request('POST', '/v2/api/cards/3/block', { reason: 'suspected_fraud' });
  assert.equal(blocked.status, 200);
  assert.equal(blocked.body.status, 'blocked');
  assert.equal(blocked.body.blockedReason, 'suspected_fraud');
  assert.equal(blocked.body.blockedAt, '2026-08-25T00:00:00.000Z');

  const repeated = await request('POST', '/v2/api/cards/3/block', { reason: 'lost' });
  assert.equal(repeated.status, 200);
  assert.deepEqual(repeated.body, blocked.body);

  const readback = await request('GET', '/v2/api/cards/3');
  assert.equal(readback.body.status, 'blocked');
});

test('blocking an unknown card returns 404', async () => {
  const response = await request('POST', '/v2/api/cards/999/block', { reason: 'lost' });
  assert.equal(response.status, 404);
  assert.equal(response.body.error, 'card_not_found');
});

test('creating a notification validates the customer and persists the record', async () => {
  const missingCustomer = await request('POST', '/v2/api/notifications', {
    customerId: 999,
    type: 'security',
    title: 'Card blocked',
    message: 'A card was blocked after suspected fraud.',
  });
  assert.equal(missingCustomer.status, 404);
  assert.equal(missingCustomer.body.error, 'customer_not_found');

  const invalid = await request('POST', '/v2/api/notifications', { customerId: 2 });
  assert.equal(invalid.status, 400);

  for (const body of [
    { customerId: 2, type: 'marketing', title: 'Card blocked', message: 'Blocked.' },
    { customerId: 2, type: 'security', title: 'Card blocked', message: 'Blocked.', priority: 'urgent' },
    { customerId: 2, type: 'security', title: 'x'.repeat(121), message: 'Blocked.' },
    { customerId: 2, type: 'security', title: 'Card blocked', message: 'x'.repeat(501) },
  ]) {
    const response = await request('POST', '/v2/api/notifications', body);
    assert.equal(response.status, 400);
    assert.equal(response.body.error, 'invalid_notification');
  }

  const created = await request('POST', '/v2/api/notifications', {
    customerId: 2,
    type: 'security',
    title: 'Card blocked',
    message: 'Your synthetic card ending 7756 was blocked after suspected fraud.',
    priority: 'high',
  });
  assert.equal(created.status, 201);
  assert.equal(created.body.customerId, 2);
  assert.equal(created.body.date, '2026-08-25T00:00:00.000Z');
  assert.equal(created.body.read, false);

  const defaultPriority = await request('POST', '/v2/api/notifications', {
    customerId: 2,
    type: 'security',
    title: 'Card blocked',
    message: 'Default priority notification.',
  });
  assert.equal(defaultPriority.status, 201);
  assert.equal(defaultPriority.body.priority, 'high');

  const readback = await request('GET', '/v2/api/notifications?customerId=2');
  assert.ok(readback.body.some((item) => item.id === created.body.id));
});

test('reset command restores the exact seed and requires a restart for a running server', async () => {
  const resetDb = path.join(tempDir, 'reset-db.json');
  fs.writeFileSync(resetDb, '{"customers":[]}\n');
  const result = spawnSync(process.execPath, ['scripts/reset.js', '--db', resetDb, '--seed', SEED_FILE], {
    cwd: ROOT,
    encoding: 'utf8',
  });
  assert.equal(result.status, 0, result.stderr);
  assert.deepEqual(JSON.parse(fs.readFileSync(resetDb, 'utf8')), JSON.parse(fs.readFileSync(SEED_FILE, 'utf8')));
});
