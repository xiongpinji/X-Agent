# Feedback Dashboard

The authenticated `/feedback` route exposes the feedback capabilities that are implemented by the backend.

## Available capabilities

- Create, list, view, update, resolve, and delete feedback.
- Tenant- and user-scoped statistics, trends, sentiment, and category summaries.
- Search feedback and export tenant-authorized records as CSV or JSON.
- Production storage is PostgreSQL only; the file store is limited to development.

## Explicitly unavailable

- Email or Slack notification configuration.
- PDF export.
- Persisted response notes. Resolving an item records its resolved status and timestamp only.

Unavailable capabilities are hidden from the dashboard rather than represented by non-functional controls.

## Verification

Run the focused frontend checks from `frontend/`:

```bash
npx vitest run src/__tests__/services/feedback.test.ts src/__tests__/pages/FeedbackDashboard.test.tsx src/__tests__/components/feedback.test.tsx
npm run type-check
npm run lint
npm run build
```

The backend surface is covered by `tests/test_feedback_commercial_surface.py` and `tests/test_feedback.py`.
