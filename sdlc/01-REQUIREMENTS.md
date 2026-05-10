# Stage 1: Requirements Elicitation

> **Skill**: `/requirements`
> **Input**: Raw text, meeting notes, slack messages, or a rough idea.
> **Output**: `.agent-spec/sdlc/01-requirements.md`

## The Goal
Convert human brain-dumps into a structured format that highlights missing information. Agents often hallucinate missing business requirements if they aren't explicitly provided. This stage forces clarification.

## Process

When the `/requirements` skill is invoked, the agent must:

1. **Read** the raw input provided by the user.
2. **Structure** the input into standard categories:
   - Problem Statement
   - Target Audience
   - Core Features
   - Out of Scope
3. **Identify Gaps**: Crucially, the agent must identify what is *missing*.
   - Are edge cases defined?
   - Is there a success metric?
   - Are there constraints (budget, timeline)?
4. **Tag**: Place `[NEEDS CLARIFICATION]` tags where information is missing.
5. **Ask**: Present a numbered list of questions to the user to fill the gaps.

## Example Output Structure

```markdown
# Requirements Document

## 1. Problem Statement
Users currently forget their passwords and have to contact support, which costs the company money.

## 2. Target Audience
Existing registered users on the web platform.

## 3. Core Features
- Users can request a password reset via email.
- Users click a secure link to enter a new password.
- Link expires after [NEEDS CLARIFICATION: How long?].

## 4. Out of Scope
- SMS/Phone based password resets.
- Changing password while already logged in.

## Open Questions for Developer
1. How long should the reset link be valid? (e.g., 15 mins, 24 hours)
2. Do we need to lock the account after X failed reset attempts?
```

The user and agent iterate on this document until no `[NEEDS CLARIFICATION]` tags remain.
