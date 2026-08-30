# Technical Debt Register

> **Location**: `.agent-spec/TECH-DEBT-REGISTER.md`
> Technical debt is normal, but it must be documented. The `@REFACTOR` persona and the `/agent-spec-debt` skill interact with this file.

---

## Active Technical Debt

| ID | Date Logged | Component | Description | Severity | Fix Effort | Status |
|----|-------------|-----------|-------------|----------|------------|--------|
| `DEBT-001` | YYYY-MM-DD | `UserService.java` | The `createUser` method is 300 lines long and handles email dispatch directly instead of using an event listener. Violates SRP. | HIGH | Medium | OPEN |
| `DEBT-002` | YYYY-MM-DD | `database` | `orders` table missing an index on `customer_id`, causing slow lookups. | MEDIUM | Low | OPEN |

## Resolved Debt

| ID | Date Resolved | Component | Resolution |
|----|---------------|-----------|------------|
| `DEBT-000` | YYYY-MM-DD | `AuthFilter` | Replaced custom JWT validation with standard Spring Security OAuth2 resource server library. |

---

## How to Log Debt
When the agent discovers a violation of SOLID or Clean Code principles but is not currently tasked with fixing it (e.g., during a feature implementation), it must:
1. Log a new entry in the "Active Technical Debt" table.
2. Alert the human developer that debt was logged.

## Debt Severity Definitions
- **CRITICAL**: Security vulnerability, data loss risk, or massive performance bottleneck. Must fix before next release.
- **HIGH**: Major architectural violation (God object, circular dependency) that slows down development.
- **MEDIUM**: Code smell, missing test coverage, or minor inefficiency.
- **LOW**: Style violation or minor cleanup needed.
