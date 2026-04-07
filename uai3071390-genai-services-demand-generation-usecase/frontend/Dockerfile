# ── Frontend Dockerfile (production) ─────────────────────────────────────────
# Two-stage build:
#   Stage 1 (build)  — compiles the Vite/React app to a static dist/
#   Stage 2 (serve)  — nginx serves dist/ and proxies /api to the orchestrator
#
# Build:
#   docker build -t sdg-frontend .
# Run standalone:
#   docker run -p 8080:8080 sdg-frontend
# nginx routes /api/ → data-service:8086 and /api/v1/chat → qna-agent:8085
# (see frontend/nginx.conf; orchestrator is not directly exposed through nginx).

# ── Stage 1: Build ────────────────────────────────────────────────────────────
FROM node:24-alpine AS build

# Corporate proxy support — pass via --build-arg or compose build.args
ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG NO_PROXY
ENV HTTP_PROXY=$HTTP_PROXY \
    HTTPS_PROXY=$HTTPS_PROXY \
    NO_PROXY=$NO_PROXY

# Trust the GE corporate CA (Zscaler SSL inspection)
# NODE_EXTRA_CA_CERTS is respected by Node.js, pnpm, and corepack natively —
# no Alpine package manager access needed.
COPY certs/GE_External_Root_CA_2_1.crt /usr/local/share/ca-certificates/GE_External_Root_CA_2_1.crt
ENV NODE_EXTRA_CA_CERTS=/usr/local/share/ca-certificates/GE_External_Root_CA_2_1.crt

# Mirror the host .npmrc for the corporate Zscaler proxy (build stage only).
# Strips any existing scheme then re-adds http:// so npm/pnpm always get a
# valid proxy URL regardless of whether the ARG was passed with or without it.
RUN echo "strict-ssl=false" > /root/.npmrc && \
    if [ -n "${HTTP_PROXY}" ]; then \
      P="${HTTP_PROXY#http://}"; P="${P#https://}"; \
      printf 'proxy=http://%s\nhttps-proxy=http://%s\n' "$P" "$P" >> /root/.npmrc; \
    fi

# Install pnpm via npm (npm respects strict-ssl; corepack has its own TLS stack)
RUN npm install -g pnpm@10.32.1

WORKDIR /app

# Install dependencies first (cache layer — only re-runs if lockfile changes)
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile

# Copy source and compile
COPY . .
# VITE_ENABLE_MOCKS=true activates MSW in the production bundle (used in compose
# until the real backend APIs are wired up).
ARG VITE_ENABLE_MOCKS=false
ENV VITE_ENABLE_MOCKS=$VITE_ENABLE_MOCKS
RUN pnpm build

# ── Stage 2: Serve ────────────────────────────────────────────────────────────
FROM nginx:alpine

# Copy compiled assets
COPY --from=build /app/dist /usr/share/nginx/html

# Custom nginx config: SPA fallback + /api proxy to orchestrator
# Placed in /templates/ so the nginx image runs envsubst on startup,
# substituting ${NGINX_RESOLVER} and ${SERVICE_NAMESPACE} from env.
COPY nginx.conf /etc/nginx/templates/default.conf.template

# NGINX_PORT default matches compose and the nginx.conf template default.
# Override to 80 for AWS ECS (ALB target-group registers the container on 80).
ARG NGINX_PORT=8080

EXPOSE ${NGINX_PORT}

CMD ["nginx", "-g", "daemon off;"]
