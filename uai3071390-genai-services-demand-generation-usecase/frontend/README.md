# Frontend - SDG Risk Analysis UI

React + Vite frontend for assessment creation, analysis review, narrative visibility, and chat.

## Stack

- React 19 + TypeScript
- Vite 7
- Redux Toolkit
- MUI 7
- Vitest + React Testing Library
- Playwright
- MSW (opt-in)

## Local Development

```bash
cd frontend
pnpm install
pnpm dev
```

Dev server runs on http://localhost:4000.

## Proxy Behavior (vite)

- /api/* -> data-service, rewritten to /dataservices/api/v1/*
- /qna/* -> qna-agent (prefix removed before forwarding)

Defaults:

- VITE_DATA_SERVICE_URL=http://localhost:8086
- VITE_QNA_AGENT_URL=http://localhost:8087

## Docker (compose)

Frontend container serves on port 3000 and proxies backend traffic via nginx template settings.

```bash
cd sdg-usecase
docker compose up --build frontend
```

## Tests and Checks

```bash
cd frontend
pnpm lint
pnpm type-check
pnpm test:run
pnpm test:e2e
```

## Project Layout

```text
frontend/
├── src/
│   ├── components/
│   ├── pages/
│   ├── store/
│   ├── routes/
│   ├── mocks/
│   └── theme/
├── e2e/
├── Dockerfile
├── nginx.conf
├── vite.config.ts
├── vitest.config.ts
└── playwright.config.ts
```
