# Knowledge Graph Specification (Graphify)

> **Location**: `.agent-spec/graph/KNOWLEDGE-GRAPH.md`
> This document visualizes the `.agent-spec/graph/knowledge-graph.json` file. The agent uses this to understand system dependencies without having to read every file.

---

# Knowledge Graph

**Project**: `[Project Name]`
**Stack**: `[Tech Stack]`
**Indexed**: `YYYY-MM-DD`

## Architecture Overview

\`\`\`mermaid
graph TD
  AuthController -->|uses| PasswordResetService
  PasswordResetService -->|uses| UserRepository
  PasswordResetService -->|uses| TokenRepository
  PasswordResetService -->|uses| EmailAdapter
  EmailAdapter -.->|external| AWS_SES
\`\`\`

## Node Inventory

| Node | Type | Path | Last Updated |
|------|------|------|-------------|
| `AuthController` | Controller | `src/main/.../AuthController.java` | YYYY-MM-DD |
| `PasswordResetService` | Service | `src/main/.../PasswordResetService.java` | YYYY-MM-DD |
| `TokenRepository` | Repository | `src/main/.../TokenRepository.java` | YYYY-MM-DD |
| `EmailAdapter` | Adapter | `src/main/.../EmailAdapter.java` | YYYY-MM-DD |

## Dependency Rules
- **Controller → Service**: Permitted.
- **Service → Repository**: Permitted.
- **Repository → Service**: **VIOLATION** (Circular/Layering).
- **Service → Controller**: **VIOLATION** (Layering).

## How to Update This Graph
When the agent executes Gate 3 (Architecture), it must evaluate if the proposed LLD introduces new nodes or edges. If so, it must:
1. Ensure the new edge does not create a circular dependency.
2. Update the Mermaid diagram.
3. Update the JSON graph data.
