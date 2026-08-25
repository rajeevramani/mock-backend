'use strict';

const path = require('node:path');
const jsonServer = require('json-server');

const PORT = Number(process.env.PORT || 10097);
const HOST = process.env.HOST || '0.0.0.0';
const DB_FILE = path.resolve(process.env.DB_FILE || 'db.json');
const BLOCK_REASONS = new Set(['suspected_fraud', 'lost', 'stolen']);

const server = jsonServer.create();
const router = jsonServer.router(DB_FILE);

server.use(jsonServer.defaults());
server.use(jsonServer.bodyParser);

server.get('/healthz', (_request, response) => {
  response.json({ status: 'ok', service: 'mockbank-banking-sandbox' });
});

server.get('/readyz', (_request, response) => {
  try {
    router.db.getState();
    response.json({ status: 'ready', database: 'available' });
  } catch (_error) {
    response.status(503).json({ status: 'not_ready', database: 'unavailable' });
  }
});

function requireRelatedRecord(queryName, collectionName, missingError, notFoundError) {
  return (request, response, next) => {
    const rawId = request.query[queryName];
    const id = Number(rawId);
    if (rawId === undefined || rawId === '' || !Number.isInteger(id) || id <= 0) {
      return response.status(400).json({ error: missingError });
    }
    if (!router.db.get(collectionName).find({ id }).value()) {
      return response.status(404).json({ error: notFoundError });
    }
    return next();
  };
}

const requireCustomerId = requireRelatedRecord(
  'customerId',
  'customers',
  'customer_id_required',
  'customer_not_found',
);
const requireAccountId = requireRelatedRecord(
  'accountId',
  'accounts',
  'account_id_required',
  'account_not_found',
);

server.get('/v2/api/accounts', requireCustomerId);
server.get('/v2/api/cards', requireCustomerId);
server.get('/v2/api/notifications', requireCustomerId);
server.get('/v2/api/transactions', requireAccountId);

server.post('/v2/api/cards/:id/block', (request, response) => {
  const cardId = Number(request.params.id);
  const reason = request.body && request.body.reason;
  if (!BLOCK_REASONS.has(reason)) {
    return response.status(400).json({
      error: 'invalid_block_reason',
      message: `reason must be one of: ${Array.from(BLOCK_REASONS).join(', ')}`,
    });
  }

  const card = router.db.get('cards').find({ id: cardId }).value();
  if (!card) {
    return response.status(404).json({ error: 'card_not_found' });
  }
  if (card.status === 'blocked') {
    return response.json(card);
  }

  const blocked = {
    ...card,
    status: 'blocked',
    blockedAt: process.env.DEMO_NOW || new Date().toISOString(),
    blockedReason: reason,
  };
  router.db.get('cards').find({ id: cardId }).assign(blocked).write();
  return response.json(blocked);
});

server.post('/v2/api/notifications', (request, response) => {
  const body = request.body || {};
  const required = ['customerId', 'type', 'title', 'message'];
  const missing = required.filter((field) => body[field] === undefined || body[field] === '');
  const allowed = new Set([...required, 'priority']);
  const unknown = Object.keys(body).filter((field) => !allowed.has(field));
  const validPriority = body.priority === undefined || ['normal', 'high'].includes(body.priority);
  const validStrings =
    body.type === 'security' &&
    typeof body.title === 'string' && body.title.length >= 1 && body.title.length <= 120 &&
    typeof body.message === 'string' && body.message.length >= 1 && body.message.length <= 500;
  if (missing.length > 0 || unknown.length > 0 || !validPriority || !validStrings) {
    return response.status(400).json({
      error: 'invalid_notification',
      message: 'notification must match the curated security-notification contract',
    });
  }

  const customerId = Number(body.customerId);
  if (!Number.isInteger(customerId) || customerId <= 0) {
    return response.status(400).json({ error: 'invalid_notification' });
  }
  const customer = router.db.get('customers').find({ id: customerId }).value();
  if (!customer) {
    return response.status(404).json({ error: 'customer_not_found' });
  }

  const notifications = router.db.get('notifications');
  const nextId = Math.max(0, ...notifications.value().map((item) => Number(item.id))) + 1;
  const notification = {
    id: nextId,
    customerId,
    type: body.type,
    title: body.title,
    message: body.message,
    date: process.env.DEMO_NOW || new Date().toISOString(),
    read: false,
    priority: body.priority || 'high',
  };
  notifications.push(notification).write();
  return response.status(201).json(notification);
});

server.use('/v2/api', router);

const listener = server.listen(PORT, HOST, () => {
  console.log(`MockBank JSON Server is running on http://${HOST}:${PORT}/v2/api`);
});

function shutdown() {
  listener.close(() => process.exit(0));
}

process.on('SIGINT', shutdown);
process.on('SIGTERM', shutdown);
