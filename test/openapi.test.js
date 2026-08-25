'use strict';

const assert = require('node:assert/strict');
const path = require('node:path');
const SwaggerParser = require('@apidevtools/swagger-parser');
const { test } = require('node:test');

const SPEC = path.resolve(__dirname, '..', 'openapi.flowplane-demo.yaml');
const EXPECTED_OPERATIONS = [
  'blockCard',
  'createCustomerNotification',
  'getCustomer',
  'listAccountTransactions',
  'listCustomerAccounts',
  'listCustomerCards',
  'listCustomerNotifications',
];

function operations(document) {
  return Object.entries(document.paths).flatMap(([pathname, pathItem]) =>
    Object.entries(pathItem)
      .filter(([method]) => ['get', 'post', 'put', 'patch', 'delete'].includes(method))
      .map(([method, operation]) => ({ pathname, method, operation })),
  );
}

test('curated Flowplane contract is valid and exposes only the investigation journey', async () => {
  const document = await SwaggerParser.validate(SPEC);
  assert.equal(document.openapi, '3.0.3');
  assert.equal(document.servers[0].url, 'http://localhost:10097');
  assert.match(document.info.description, /synthetic/i);

  const entries = operations(document);
  const ids = entries.map(({ operation }) => operation.operationId).sort();
  assert.deepEqual(ids, EXPECTED_OPERATIONS);
  assert.equal(new Set(ids).size, ids.length);

  for (const { pathname, method, operation } of entries) {
    assert.ok(operation.description, `${method.toUpperCase()} ${pathname} needs an agent-facing description`);
    assert.ok(operation.responses['400'] || method === 'get', `${operation.operationId} must document 400`);
    assert.ok(operation.responses['404'], `${operation.operationId} must document 404`);
  }
});

test('contract paths correspond to the JSON Server and custom middleware routes', async () => {
  const document = await SwaggerParser.parse(SPEC);
  assert.deepEqual(Object.keys(document.paths).sort(), [
    '/v2/api/accounts',
    '/v2/api/cards',
    '/v2/api/cards/{id}/block',
    '/v2/api/customers/{id}',
    '/v2/api/notifications',
    '/v2/api/transactions',
  ]);
});

test('notification response schema is satisfiable under strict additional-property validation', async () => {
  const document = await SwaggerParser.parse(SPEC);
  const notification = document.components.schemas.Notification;
  assert.equal(notification.type, 'object');
  assert.equal(notification.additionalProperties, false);
  assert.equal(notification.allOf, undefined);
  assert.deepEqual(
    notification.required,
    ['id', 'customerId', 'type', 'title', 'message', 'priority', 'date', 'read'],
  );
  assert.deepEqual(notification.properties.type, { type: 'string' });
});
