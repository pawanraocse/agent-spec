# Stage 2: Technical Specification

> **Skill**: `/agent-spec-tech-spec`
> **Input**: `.agent-spec/sdlc/01-REQUIREMENTS.md`
> **Output**: `.agent-spec/sdlc/02-TECH-SPEC.md`

## The Goal
Assess the technical feasibility of the requirements, choose the appropriate technology stack, and define non-functional requirements (NFRs) before writing detailed product stories.

## Process

When the `/agent-spec-tech-spec` skill is invoked, the agent must:

1. **Load** the requirements document.
2. **Assess Feasibility**: Can this be built with the current tech stack? (Check `PROJECT-INDEX.md`).
3. **Define Stack Choices**: Specify libraries, APIs, or infrastructure needed. If a new dependency is required, the agent must justify it.
4. **Define NFRs**: Outline performance, security, scale, and availability constraints with measurable thresholds.
5. **Identify Risks**: Document potential technical roadblocks.
6. **Assign Complexity Score**: The SDLC router reads this to decide which design gates to run.

## Example Output Structure

```markdown
# Technical Specification

## 1. Feasibility Assessment
The password reset feature is highly feasible using our existing Java Spring Boot stack.
We will need to integrate an email provider.

## 2. Technology Choices
- **Backend**: Spring Boot Security (existing)
- **Token Generation**: JWT (Recommendation: JWT for statelessness)
- **Email Service**: AWS SES (via existing AWS SDK dependency)
- **Database**: PostgreSQL (existing `users` table)

## 3. Non-Functional Requirements (NFRs)
- **NFR-001 Security**: Reset tokens must be one-time use only. Must be hashed in the database.
  Measure: Integration test asserts token is invalidated after first use.
- **NFR-002 Performance**: Email dispatch must be asynchronous so the API responds in < 200 ms.
  Measure: Load test at 500 RPS; p95 < 200 ms.
- **NFR-003 Availability**: Standard 99.9% uptime.
  Measure: Uptime monitor; 30-day SLA report.

## 4. Technical Risks & Mitigations
- **Risk**: Malicious actors spamming the reset endpoint to enumerate users.
- **Mitigation**: Always return generic "If an account exists, an email was sent" response.
  Apply rate limiting (max 3 requests per hour per IP).

## Complexity
Scope: narrow
Algorithm: low
Track: fast-track
Rationale: Change is confined to one controller and one service class; no novel algorithm required.
```

## Complexity field reference

The `## Complexity` section is read by `/agent-spec-sdlc` to select the correct gate track.
Fill it at the end of every tech-spec.

| Field | Values | Meaning |
|---|---|---|
| Scope | `narrow` / `wide` | narrow = ≤ 3 files, one service; wide = cross-service, schema, new API |
| Algorithm | `low` / `high` | high = novel data structure, state machine, crypto, multi-site schema migration |
| Track | `fast-track` / `algorithm` / `design` / `full` | derived from the 2×2 matrix in `/agent-spec-sdlc` |
| Rationale | one sentence | justifies the track — prevents silent misclassification |
