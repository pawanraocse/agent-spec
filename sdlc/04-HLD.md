# Stage 4: High Level Design (HLD)

> **Skill**: `/agent-spec-hld`
> **Input**: `.agent-spec/sdlc/03-prd.md` & `02-tech-spec.md`
> **Output**: `.agent-spec/sdlc/04-hld.md`

## The Goal
Translate the Product Requirements (WHAT) into a System Architecture (HOW at a macro level). The HLD defines the components, data flows, and major technical decisions required to satisfy the PRD.

## Process

When the `/agent-spec-hld` skill is invoked, the `@ARCHITECT` persona automatically takes over. The agent must:

1. **Load Context**: Read the PRD, Tech Spec, and the project's `KNOWLEDGE-GRAPH.md`.
2. **Component Mapping**: Identify which existing services/modules will be modified, and which new ones will be created.
3. **Data Flow**: Describe how data moves through the system to satisfy the primary user journeys.
4. **Draw the Architecture**: Generate a Mermaid diagram representing the new state of the system.
5. **Security & Scale**: Address NFRs (Non-Functional Requirements) defined in the Tech Spec.

## Example Output Structure

```markdown
# High Level Design

## 1. System Context
This feature extends the `auth-service` to handle password resets, interacting with the existing `user-db` and a new external `email-provider` integration.

## 2. Component Architecture
- **AuthController**: Exposes new REST endpoints for reset requests and confirmation.
- **PasswordResetService**: Handles token generation, validation, and expiration logic.
- **EmailAdapter**: Abstracts the AWS SES integration.

## 3. Data Flow Diagram
\`\`\`mermaid
sequenceDiagram
    participant User
    participant AuthController
    participant PasswordResetService
    participant EmailAdapter
    
    User->>AuthController: POST /reset-request {email}
    AuthController->>PasswordResetService: generateToken(email)
    PasswordResetService-->>AuthController: token
    AuthController->>EmailAdapter: sendResetEmail(email, token)
    EmailAdapter-->>User: Delivery
\`\`\`

## 4. API Boundaries (Macro)
- **New Internal APIs**: None
- **New External APIs**: `POST /api/v1/auth/password-reset`
- **Third-Party Integrations**: AWS SES for transactional email.

## 5. Security Considerations
- Rate limiting must be applied at the API Gateway level to prevent email enumeration.
- Tokens must be cryptographically secure (`SecureRandom`) and hashed before DB storage.
```
