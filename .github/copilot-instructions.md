# Zendesk — IT Support Ticket System Project Instructions

This file is the single source of truth for contributors and coding agents. If another project document conflicts with it, follow this file and update the stale document as part of the same change.

## Product and architecture

- Build a small-organization IT support ticket system for employees and support staff.
- The frontend is semantic HTML, CSS, and vanilla JavaScript in separate files. The backend is FastAPI (Python) with SQLite. Do not add a frontend framework.
- Keep the implementation dependency-light. Add Python dependencies only when needed and declare each runtime/development dependency in `requirements.txt`.
- Persist tickets, SLA timestamps, and audit history in SQLite; `localStorage` may be used only for temporary UI state or a backward-compatible import path, not as the source of truth.
- The ticket lifecycle is `Open`, `In Progress`, and `Resolved`. Do not add or remove a state without updating the API, UI, database constraints/migration, documentation, and tests together.
- Preserve existing ticket fields and API response shapes when extending them. Make database changes backward-compatible, migrate explicitly, and never discard existing local browser data silently.

## Non-negotiable accessibility

- Target WCAG 2.1 AA. Use semantic structure, programmatically associated labels, keyboard-operable controls, visible focus, responsive layouts, and clear status/error announcements.
- Every high or critical priority ticket shown in a list, board, table, or detail view must use all of the following at once:
  1. An explicit visible text label: `HIGH PRIORITY` or `CRITICAL`.
  2. A distinct geometric SVG icon with `aria-hidden="true"`; do not substitute emoji or Unicode symbols for the icon.
  3. A distinct 2px structural border and high-contrast surface treatment.
  4. Accessible priority text through an `aria-label`, `aria-describedby`, or equivalent screen-reader markup.
- Never use red, hue, or any other color as the sole priority/status signal. Text and shape must retain the meaning in monochrome and common color-vision deficiencies.
- Maintain at least 4.5:1 contrast for normal text and icons against their backgrounds. Verify contrast for interactive states as well as the default state.
- Do not claim WCAG conformance solely because automated checks pass; describe the checks actually performed.

## Design system

- Use Plus Jakarta Sans, Geist Sans, or Inter Tight for interface typography when available; provide robust local fallbacks and do not make the app depend on an unavailable external font service.
- Use JetBrains Mono or Geist Mono for ticket IDs and time measurements. Apply `font-variant-numeric: tabular-nums` to IDs/counters/timers where it improves scanning.
- Establish a clear typographic hierarchy: strong, tightly tracked headings; readable body copy; restrained uppercase utility labels.
- Use the blue-and-white product palette, legible contrast, subtle borders and purposeful depth. Do not make red the primary interface color.
- Motion must be brief and purposeful, respect `prefers-reduced-motion`, and never be required to understand state. Provide visible hover, focus, active, loading, error, and empty states as relevant.
- Empty and filtered states must explain what happened and offer an appropriate next action, such as clearing a filter or creating a ticket.

## Product truth and telemetry

- Never invent operational health, customer, SLA, service-level, security, privacy, or certification claims.
- In mock/local-demo mode, visibly label all sample KPIs and seeded/sample data `Illustrative Demo Content`. Do not imply sample values measure the organization or live service.
- In full-stack mode, derive displayed ticket counts and SLA metrics from actual SQL aggregations over persisted ticket records. Expose metric provenance/state in the API and UI.
- Calculate response-time and SLA metrics only from recorded timestamps and a defined SLA target. Exclude records without the required timestamps from the applicable denominator; return an explicit unavailable/null value when no eligible records exist.
- A live health indicator must be based on a real backend health check, including SQLite connectivity. A client-only heartbeat may claim only that the page/client is ready, never that the server or organization is operational.
- A database-backed audit log is an audit trail, not evidence of SOC 2, ISO certification, or compliance. State certifications only when verified evidence is provided.

## API and data integrity

- Keep the API small and documented. The system health route is `GET /api/health`; ticket routes support list/filter, lookup, create, and status/priority updates; metrics come from SQL aggregation.
- Validate request bodies and query parameters at the API boundary. Use parameterized SQL and explicit transactions for writes.
- Every successful status or priority change must create an immutable audit-log record in the same transaction.
- Keep ticket status and priority values constrained and consistent across API validation, schema, and frontend controls.
- Return explicit HTTP error statuses and actionable messages. Do not hide failures, return success-shaped fallbacks, or silently treat database errors as empty data.
- Protect destructive operations with an explicit user action and confirmation. Escape/render user-provided values as text; never inject them as HTML.

## Code hygiene and scope

- Read relevant instructions, requirements, implementation, and tests before editing.
- Make the smallest complete change that addresses the request. Modify only necessary files; do not reformat unrelated code or remove existing workflows.
- Preserve backward compatibility for stored data, ticket fields, routes, and response shapes. If compatibility cannot be maintained, explain the migration and keep it lossless.
- Prefer clear descriptive names and small single-purpose functions. Avoid duplicated logic, needless abstractions, broad exception handling, and unexplained comments.
- Do not add an unrelated feature or claim. Update README and tests whenever behavior, setup, API, or data contracts change.

## Required verification and delivery

- Before claiming completion, run the relevant Python tests, JavaScript syntax check, and project build/start validation available for the change. Do not claim a command passed unless it ran successfully.
- Exercise API health/database connectivity, ticket create/read/filter/update, audit logging, and metric aggregation where affected. Exercise UI keyboard/focus behavior, high-priority cues, quick lookup, and responsive layout when changed.
- Report commands and outcomes accurately. If a check is blocked, state why and provide reproducible manual steps rather than implying it passed.
- Give numbered manual verification steps with preconditions, exact actions, and expected results.
- Summarize changed behavior, data compatibility, instruction/accessibility compliance, and remaining verification needs.
