# Frontend E2E Tests

Playwright end-to-end tests for the SDG frontend.

## Commands

```bash
cd frontend
pnpm test:e2e
pnpm test:e2e:ui
pnpm test:e2e:debug
```

## Configuration Summary

- Test directory: e2e/
- Base URL: http://localhost:4000
- Browser project: chromium
- Retries: CI only
- HTML report enabled
- Dev server auto-start command: pnpm dev

## Guidelines

1. Prefer user-flow assertions over implementation details.
2. Use stable selectors (role, label, or data-testid when needed).
3. Avoid fixed sleeps; rely on Playwright waiting.
4. Keep tests isolated and data-independent.
