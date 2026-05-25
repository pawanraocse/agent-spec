# Cursor Skill: review

**Description**: Deep skeptical code review.

## Instructions for Cursor
1. Adopt the @REVIEWER persona.
2. Run `./.agent-spec/bin/graphify-cli.py query --file <target_file>` to understand what depends on the file being reviewed.
3. Review the specified files against coding-standards/CLEAN-CODE.md AND coding-standards/SIMPLICITY-FIRST.md.
4. Identify logic flaws, style violations, and missing tests.
5. Output findings using [BLOCKER], [MINOR], and [NIT] tags.
