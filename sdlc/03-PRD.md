# Stage 3: Product Requirements Document (PRD)

> **Skill**: `/agent-spec-prd`
> **Input**: `.agent-spec/sdlc/01-REQUIREMENTS.md` & `02-TECH-SPEC.md`
> **Output**: `.agent-spec/sdlc/03-PRD.md`

## The Goal
Convert approved requirements into a formal Product Requirements Document. A PRD defines exactly *what* is being built, for *whom*, and *why*, with strict acceptance criteria. **It contains NO technical implementation details.**

## The PRD Cycle Pattern

The agent must use an iterative Discover → Document → Review cycle to build the PRD:

1. **Discover**: Identify missing user journeys, edge cases, or metrics. Ask questions if needed.
2. **Document**: Draft the section using the MoSCoW method. Use `[NEEDS CLARIFICATION]` tags for any assumed values.
3. **Review**: Validate the section against the 14-Point Checklist (see below) before finalizing.

## MoSCoW Prioritization

Every feature in the PRD must be categorized:
- **[Must Have]**: Non-negotiable core functionality.
- **[Should Have]**: Important, but the product functions without it.
- **[Could Have]**: Nice to have if time permits.
- **[Won't Have]**: Explicitly out of scope for this iteration.

## The 14-Point Validation Checklist

Before finalizing the PRD, the agent must verify all 14 points:

- [ ] 1. All required sections are complete
- [ ] 2. No `[NEEDS CLARIFICATION]` markers remain (or they are explicitly accepted by user)
- [ ] 3. Problem statement is specific and measurable
- [ ] 4. Problem is validated by evidence (not assumptions)
- [ ] 5. Context → Problem → Solution flow makes sense
- [ ] 6. Every persona has at least one user journey
- [ ] 7. All MoSCoW categories are addressed
- [ ] 8. Every feature has testable acceptance criteria (Given/When/Then format)
- [ ] 9. Every metric has corresponding tracking events defined
- [ ] 10. No feature redundancy or duplicate stories
- [ ] 11. No contradictions between sections
- [ ] 12. **No technical implementation details included** (e.g., no DB schemas or API routes)
- [ ] 13. Edge cases and error states are documented
- [ ] 14. A new team member could read this and understand the exact goal

## Output Status Report

When the `/agent-spec-prd` skill finishes, the agent should output a status report in the chat:

```markdown
📝 **PRD Status Generated**
- Sections Complete: 5/5
- Validation Status: 12/14 passed
- ⚠️ Pending: Needs clarification on [Edge Case X].
```
