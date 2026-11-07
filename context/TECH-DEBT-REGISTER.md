# Technical Debt Register

> **Location**: `.agent-spec/TECH-DEBT-REGISTER.md`
> Technical debt is normal, but it must be documented. The `@REFACTOR` persona and the `/agent-spec-debt` skill interact with this file.

---

## Active Technical Debt

| ID | Date Logged | Component | Description | Severity | Fix Effort | Status |
|----|-------------|-----------|-------------|----------|------------|--------|
| _none logged_ | | | Add a row per defect risk found outside the current task. | | | |

## Resolved Debt

| ID | Date Resolved | Component | Resolution |
|----|---------------|-----------|------------|
| _none_ | | | |

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
