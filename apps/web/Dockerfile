# Web app image (Next.js standalone). Build context is the repo root.
FROM node:22-alpine AS deps
WORKDIR /app/apps/web
COPY apps/web/package.json apps/web/package-lock.json ./
RUN npm ci --no-audit --no-fund

FROM node:22-alpine AS build
WORKDIR /app/apps/web
ENV NEXT_TELEMETRY_DISABLED=1
COPY --from=deps /app/apps/web/node_modules ./node_modules
COPY apps/web/ ./
RUN npm run build

FROM node:22-alpine AS run
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 PORT=3000 HOSTNAME=0.0.0.0
RUN addgroup -S web && adduser -S web -G web
COPY --from=build --chown=web:web /app/apps/web/.next/standalone ./
COPY --from=build --chown=web:web /app/apps/web/.next/static ./.next/static
COPY --from=build --chown=web:web /app/apps/web/public ./public
USER web
EXPOSE 3000
CMD ["node", "server.js"]
