# Project Index Template

> **Location**: `.agent-spec/PROJECT-INDEX.md`
> This is a living document. The agent must update this document when new modules are added or architectural decisions are made.

---

# Project Index

## Project Overview
**Name**: `[Project Name]`
**Type**: `[web-app | api | library | monolith | microservice]`
**Tech Stack**: `[e.g., Java Spring Boot + Angular]`
**Status**: `[active | maintenance]`

## Modules / Services
| Module | Responsibility | Path | Last Updated |
|--------|---------------|------|-------------|
| `auth-service` | Handles JWT issuance and validation. | `src/main/java/.../auth/` | YYYY-MM-DD |
| `payment-service` | Stripe integration and invoice generation. | `src/main/java/.../payment/` | YYYY-MM-DD |

## Key Architectural Decisions
- **[ADR-001]**: Chose PostgreSQL for ACID compliance. No NoSQL.
- **[ADR-002]**: REST APIs must conform to standard JSON:API format.
- **[ADR-003]**: Service-to-service communication is asynchronous via Kafka events.

## Known Technical Debt
| ID | Description | Severity | Owner |
|----|-------------|----------|-------|
| `DEBT-01` | `auth-service` missing rate limiting on login endpoint. | HIGH | Backend Team |

## External Dependencies
| Name | Purpose | Version |
|------|---------|---------|
| AWS SES | Transactional email delivery | v2 |
| Stripe API | Payment processing | 2023-10-16 |

## Active Sessions
| Date | Developer | Gate | Task |
|------|-----------|------|------|
| YYYY-MM-DD | User | 4 | Implementing password reset |
