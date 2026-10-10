# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Semantic HTML, CSS, vanilla JavaScript, FastAPI, and SQLite.

## Users

Employees reporting internal IT issues and IT support staff triaging and resolving requests at a small organization.

## Product Purpose

Provide a lightweight way to create, track, search, prioritize, and resolve internal support requests. Success means employees can submit complete requests and support staff can see priority and progress clearly.

## Positioning

A compact local-run support queue with browser-based access and a single SQLite-backed source of ticket data.

## Operating Context

The app runs locally in a modern browser and connects to a local FastAPI service. Tickets are stored in SQLite. The app has no identity or authentication layer; deployment beyond a trusted local environment remains undecided.

## Capabilities and Constraints

Tickets have a title, requester, category, priority, description, status, creation time, SLA target, and optional first-response/resolution timestamps. Supported statuses are Open, In Progress, and Resolved. The app supports ticket creation, title/requester/ID search, priority filtering, status and priority changes, deletion, status counts, SQL-derived metrics, and a server/database health check. Local browser ticket records are retained and imported into SQLite idempotently. No authentication, organization-level live service feed, automated root-cause analysis, or automatic escalation exists.

## Brand Commitments

Use a blue-and-white theme. Communicate priority and status with text as well as color.

## Evidence on Hand

README.md documents the business context and supported workflows. There are no verified operational metrics, certification records, customers, or externally measured service-health data. Metrics must be calculated from persisted ticket timestamps; optional seeded data must be labeled illustrative demo content. Audit records are not certification evidence.

## Product Principles

- Keep ticket handling understandable for first-time users.
- Make urgency and progress identifiable without relying on color alone.
- Be clear about the boundaries of the local server, telemetry, and sample data.
- Validate input and report storage failures instead of implying success.

## Accessibility & Inclusion

Use semantic HTML, labeled controls, visible keyboard focus, responsive layouts, and non-color-only priority/status cues. Target WCAG 2.1 AA; automated checks do not alone establish conformance.
