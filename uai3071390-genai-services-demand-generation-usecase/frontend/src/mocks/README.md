# Frontend API Mocks (MSW)

MSW handlers used for tests and optional local browser mocking.

## Files

```text
src/mocks/
├── browser.ts   # worker setup for browser
├── node.ts      # server setup for tests
└── handlers.ts  # request handlers
```

## Enable Browser Mocks

Browser mocks are opt-in and start only when VITE_ENABLE_MOCKS=true.

```bash
cd frontend
VITE_ENABLE_MOCKS=true pnpm dev
```

Runtime behavior is implemented in src/main.tsx.

## Add a New Handler

Add route handlers in handlers.ts with path and response payloads that match frontend contracts.
