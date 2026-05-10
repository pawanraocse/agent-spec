# Project Constitution

> **Location**: `.agent-spec/CONSTITUTION.md`
> This file contains the project-specific rules that the AI agent must obey. Unlike `AGENTS.md` (which applies to the framework), this file is tailored to *your* specific codebase.

---

## 1. Project Context
- **Language**: `[e.g., Java 21, TypeScript 5.4]`
- **Framework**: `[e.g., Spring Boot 3.2, Angular 17]`
- **Primary Database**: `[e.g., PostgreSQL 16]`
- **Testing Framework**: `[e.g., JUnit 5, Jasmine/Karma]`

## 2. Hard Dependencies
The agent MUST use these libraries for these specific tasks. It must NOT introduce competing libraries (e.g., do not introduce `Gson` if we use `Jackson`).

| Task | Approved Library |
|------|------------------|
| JSON Serialization | `[e.g., Jackson]` |
| Date/Time | `[e.g., java.time.* (No java.util.Date)]` |
| HTTP Client | `[e.g., WebClient or fetch API]` |
| Logging | `[e.g., SLF4J + Logback]` |

## 3. Custom Project Rules
*(Add any specific rules the agent must follow for this project)*

1. **Rule 1**: e.g., "All DB tables must have `created_at` and `updated_at` columns."
2. **Rule 2**: e.g., "All REST endpoints must return a standard `ApiResponse<T>` wrapper."
3. **Rule 3**: e.g., "Do not use `@Data` from Lombok, use `@Getter` and `@Setter`."

## 4. Banned Practices
*(Add things the agent is explicitly forbidden from doing in this project)*

1. **Banned 1**: e.g., "Do not use `SimpleDateFormat` as it is not thread-safe."
2. **Banned 2**: e.g., "Do not use native CSS, only use Tailwind utility classes."
