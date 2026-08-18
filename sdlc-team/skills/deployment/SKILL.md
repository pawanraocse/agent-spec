---
name: deployment
description: "Prepare a release: CI/CD steps, semantic versioning, release notes, migration ordering, rollback plan, and post-deploy health checks. Load when preparing a deployment, cutting a release, or writing a rollback plan. Prepares the release; does not execute it."
---

# Deployment

This stage **prepares** a release. It does not perform one. Executing a deploy is a
human decision with human accountability — produce the plan, the commands, and the
rollback, then stop.

## Required inputs

`02-hld.md` (NFRs, dependencies), `07-qa-signoff.md` (must not be `FAIL`), and the
repo's existing CI/CD setup.

```bash
ls -1 .github/workflows/ .gitlab-ci.yml Jenkinsfile 2>/dev/null
ls -1 Dockerfile docker-compose.yml 2>/dev/null
find . -path ./node_modules -prune -o -name '*.tf' -print 2>/dev/null | head
git tag --sort=-v:refname | head -5
```

Extend the existing pipeline. Do not introduce a second deployment mechanism because
you prefer it.

## Versioning

Semantic versioning, judged by **consumer impact**, not effort:

| Bump | When |
|------|------|
| **Major** | Breaking API change, removed endpoint, incompatible migration |
| **Minor** | Backward-compatible feature |
| **Patch** | Backward-compatible fix |

A new required request field is **major**, however small the diff. Match the repo's
existing tag format (`v1.2.3` vs `1.2.3`).

## Migration ordering

The most common deploy outage is a migration that assumes code and schema change
simultaneously. They do not — during a rollout, old code runs against the new schema.

**Expand/contract, always:**

1. **Expand** — add the new column/table, nullable. Old code ignores it.
2. **Deploy** — new code writes both old and new.
3. **Backfill** — migrate existing rows.
4. **Contract** — a *later* release drops the old column.

Never combine expand and contract in one release. Never add a `NOT NULL` column without
a default to a populated table.

## Release notes

Written for whoever is paged at 3am, not for a changelog bot.

```markdown
## v1.4.0 — Password reset

### Added
- Self-service password reset by emailed link (PRD: password-reset)

### Changed
- `POST /auth/login` now returns 429 when rate limited (was 400)

### Migration
- Adds `password_reset_token`. Additive, no backfill. ~2s on production volume.

### Operational
- New env var `RESET_TOKEN_TTL` (default `15m`)
- Requires `MAILER_API_KEY` to be present — **deploy fails fast if unset**
- New alert: `password_reset_failure_rate > 5%`

### Rollback
- Safe. Revert the deploy; leave the table (unused by the previous version).
```

Call out anything that changes an existing contract, even when it looks like a fix.

## Rollback plan

Every release needs one, written before deploying, in this shape:

| | |
|---|---|
| **Trigger** | What signal says roll back — error rate, latency, alert |
| **Command** | The exact command |
| **Data** | Is it reversible? Does new-schema data survive the old code? |
| **Time** | How long the rollback takes |
| **Point of no return** | After which step rollback is no longer clean |

"Redeploy the previous tag" is not a plan if a migration already ran. State explicitly
whether the old code tolerates the new schema — this is what makes expand/contract
non-negotiable.

## Post-deploy verification

Name what you will check and what threshold triggers a rollback:

```markdown
- [ ] Health endpoint 200 across all instances
- [ ] Error rate < 1% over 10 min (baseline 0.3%)
- [ ] p95 latency < 200ms (NFR-1)
- [ ] One real reset completed end to end in production
- [ ] No new entries in the error tracker
```

## Currency

CI/CD platforms, action versions, and runtime images change frequently, and pinned
versions in this repo will drift from current. **Read the repo's existing workflow files
and match them**; verify action and image versions against current upstream rather than
reusing a version from memory. Flag anything obviously outdated (an EOL runtime, an
archived action) as a finding rather than silently copying it forward.

## Self-check before handoff

Load `handoff-validation`. Your upstream is `02-hld.md` and `07-qa-signoff.md`.

- QA verdict is not `FAIL`. If it is, stop and report — do not prepare a release for
  a feature that failed validation.
- Every HLD NFR has a post-deploy check or is flagged unmonitorable.
- Every migration has a tested rollback path.
- Every new env var or secret is documented, with its failure mode when missing.
- The version bump matches the actual consumer impact.

## Anti-patterns

- **Deploying anyway.** Preparing a release over a `FAIL` sign-off without flagging it.
- **Combined expand/contract.** Dropping the old column in the same release that adds the new.
- **Rollback by assumption.** "We can just revert" without checking data compatibility.
- **Silent config requirements.** A new required env var that surfaces as a 500 at runtime.
- **Version-by-effort.** Calling a breaking change a minor bump because it was a small diff.
