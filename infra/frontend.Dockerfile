FROM node:22-alpine AS build
WORKDIR /workspace
RUN corepack enable && corepack prepare pnpm@10.29.2 --activate
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY apps/web/package.json apps/web/package.json
COPY apps/admin/package.json apps/admin/package.json
COPY packages packages
RUN pnpm install --frozen-lockfile
COPY apps/web apps/web
COPY apps/admin apps/admin
RUN pnpm --filter @leadflow/web build && pnpm --filter @leadflow/admin build

FROM caddy:2-alpine
COPY infra/Caddyfile /etc/caddy/Caddyfile
COPY --from=build /workspace/apps/web/dist /srv/web
COPY --from=build /workspace/apps/admin/dist /srv/admin
