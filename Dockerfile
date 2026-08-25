FROM node:22-alpine

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci --omit=dev && npm cache clean --force

COPY --chown=node:node server.js ./
COPY --chown=node:node scripts ./scripts
COPY --chown=node:node fixtures ./fixtures

RUN mkdir -p /app/data \
    && cp /app/fixtures/seed.json /app/data/db.json \
    && chown -R node:node /app/data

ENV NODE_ENV=production \
    HOST=0.0.0.0 \
    PORT=10097 \
    DB_FILE=/app/data/db.json \
    SEED_FILE=/app/fixtures/seed.json

USER node

EXPOSE 10097

HEALTHCHECK --interval=5s --timeout=3s --start-period=5s --retries=12 \
  CMD ["node", "-e", "fetch('http://127.0.0.1:10097/healthz').then(r=>{if(!r.ok)process.exit(1)}).catch(()=>process.exit(1))"]

CMD ["node", "server.js"]
