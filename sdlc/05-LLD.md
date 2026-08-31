# Stage 5: Low Level Design (LLD)

> **Skill**: `/agent-spec-lld`
> **Input**: `.agent-spec/sdlc/04-HLD.md`
> **Output**: `.agent-spec/sdlc/05-LLD.md`

## The Goal
Provide the exact blueprint for the code. The LLD translates the macro architecture into specific classes, interfaces, database schemas, and JSON API payloads. **This is the final step before coding begins.**

## Process

When the `/agent-spec-lld` skill is invoked, the agent must:

1. **Load Context**: Read the HLD and `KNOWLEDGE-GRAPH.md`.
2. **Class Design**: Define the exact class names, member variables, and method signatures required.
3. **Schema Design**: Define exact database table changes (SQL DDL or ORM entities).
4. **API Contracts**: Define exact JSON request/response payloads and HTTP status codes.
5. **SOLID Check**: Verify that the proposed classes adhere to the Single Responsibility Principle.

## Example Output Structure

```markdown
# Low Level Design

## 1. Database Schema
**New Table**: `password_reset_tokens`
- `id` (UUID, Primary Key)
- `user_id` (UUID, Foreign Key -> users.id)
- `token_hash` (VARCHAR(255), Not Null)
- `expires_at` (TIMESTAMP, Not Null)

## 2. API Contracts
**POST /api/v1/auth/password-reset/request**
- **Request**: `{ "email": "user@example.com" }`
- **Response (202 Accepted)**: `{ "message": "If an account exists, an email has been sent." }`

**POST /api/v1/auth/password-reset/confirm**
- **Request**: `{ "token": "raw-token-string", "newPassword": "secure-password" }`
- **Response (200 OK)**: `{ "message": "Password updated successfully." }`
- **Response (400 Bad Request)**: `{ "error": "Invalid or expired token." }`

## 3. Class Design

\`\`\`java
@Service
public class PasswordResetService {
    private final UserRepository userRepository;
    private final TokenRepository tokenRepository;
    private final EmailPort emailPort;
    private final PasswordEncoder passwordEncoder;

    // Generates a cryptographically secure token, hashes it, saves to DB, returns raw token.
    public String createResetToken(String email) { ... }

    // Verifies token hash, updates user password, invalidates token.
    public void resetPassword(String rawToken, String newPassword) { ... }
}
\`\`\`

## 4. Testing Strategy
- **Unit Tests**: `PasswordResetServiceTest` mocking the repositories and email port.
- **Integration Tests**: Test the full controller flow with an in-memory DB and mocked external email provider.
```
