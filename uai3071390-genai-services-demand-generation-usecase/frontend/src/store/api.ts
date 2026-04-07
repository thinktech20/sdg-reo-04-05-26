/**
 * Central API configuration — single source of truth for all slice fetch calls.
 *
 * The frontend always calls /api/* (short, browser-friendly prefix).
 *
 * Routing layers translate this before it reaches the data-service container:
 *   Docker / production  → nginx rewrites  /api/* → /dataservices/api/v1/*
 *   Vite dev server      → proxy rewrites  /api/* → /dataservices/api/v1/*
 *
 * The backend (data-service) only exposes /dataservices/api/v1/* routes —
 * this is the canonical ALB-aligned path used for direct service-to-service
 * traffic in AWS. The frontend never needs to know this internal path.
 *
 * VITE_DATA_SERVICE_URL is empty in Docker (nginx handles proxying) and
 * can be set to an absolute URL when running slices in isolation outside
 * of a proxy context.
 */
// export const API_BASE = (import.meta.env.VITE_DATA_SERVICE_URL ?? '/dataservices') + '/api/v1'

export const API_BASE = '/dataservices/api/v1'
