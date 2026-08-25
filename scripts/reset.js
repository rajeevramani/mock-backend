'use strict';

const fs = require('node:fs');
const path = require('node:path');

function argument(name, fallback) {
  const index = process.argv.indexOf(name);
  return index === -1 ? fallback : process.argv[index + 1];
}

const dbFile = path.resolve(argument('--db', process.env.DB_FILE || 'db.json'));
const seedFile = path.resolve(argument('--seed', process.env.SEED_FILE || 'fixtures/seed.json'));

if (!fs.existsSync(seedFile)) {
  console.error(`Seed file does not exist: ${seedFile}`);
  process.exit(1);
}

const seed = JSON.parse(fs.readFileSync(seedFile, 'utf8'));
const temporary = `${dbFile}.reset-${process.pid}`;
fs.mkdirSync(path.dirname(dbFile), { recursive: true });
fs.writeFileSync(temporary, `${JSON.stringify(seed, null, 2)}\n`, { mode: 0o600 });
fs.renameSync(temporary, dbFile);
console.log(`Restored ${dbFile} from ${seedFile}. Restart the server if it is running.`);
