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
4. **Define NFRs**: Outline performance, security, scale, and availability constraints.
5. **Identify Risks**: Document potential technical roadblocks.

## Example Output Structure

```markdown
# Technical Specification

## 1. Feasibility Assessment
The password reset feature is highly feasible using our existing Java Spring Boot stack. We will need to integrate an email provider.

## 2. Technology Choices
- **Backend**: Spring Boot Security (existing)
- **Token Generation**: `java.util.UUID` or JWT (Recommendation: JWT for statelessness)
- **Email Service**: AWS SES (via existing AWS SDK dependency)
- **Database**: PostgreSQL (existing `users` table)

## 3. Non-Functional Requirements (NFRs)
- **Security**: Reset tokens must be one-time use only. Must be hashed in the database.
- **Performance**: Email dispatch must be asynchronous so the API responds in < 200ms.
- **Availability**: Standard 99.9%.

## 4. Technical Risks & Mitigations
- **Risk**: Malicious actors spamming the reset endpoint to enumerate users.
- **Mitigation**: Always return a generic "If an account exists, an email was sent" response regardless of email validity. Apply rate limiting (max 3 requests per hour per IP).
```
