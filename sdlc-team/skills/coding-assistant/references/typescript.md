# TypeScript / Node conventions

> Verify against the repo's `package.json` and `tsconfig.json` before applying. Tooling
> in this ecosystem turns over fast — treat everything here as a prompt to check, not a fact.

## Detect first

```bash
cat tsconfig.json 2>/dev/null | grep -E '"(strict|target|module|moduleResolution|paths)"'
grep -E '"(type|main|module|exports|engines)"' package.json
```

- `"type": "module"` → ESM: use `import`, include file extensions in relative specifiers.
- No `"type"` field → CommonJS: `require`, no extensions.
- Mixing the two is the single most common breakage. Follow the manifest.

## Types

- `strict` on: no implicit `any`, honor `strictNullChecks`. If the repo has it off, do
  not silently turn it on — that is a repo-wide change disguised as a feature commit.
- Prefer `unknown` over `any` at boundaries, then narrow.
- Prefer `type` for unions and `interface` for object contracts meant to be extended —
  but follow whichever the repo already uses consistently.
- Do not export types nobody imports.

## Structure

- One primary export per module; colocate its types.
- Barrel files (`index.ts`) only where the repo already uses them — they cost tree-shaking.
- Respect `paths` aliases in `tsconfig.json` (`@/lib/...`); do not mix with deep relatives.

## Async

- `async/await` over raw `.then()` chains.
- Never leave a floating promise. `await` it, `return` it, or explicitly `void` it.
- Use `Promise.all` for independent work; sequential `await` in a loop is usually a bug.

## Testing

Detect the runner (`vitest`, `jest`, `node --test`) and match its import style — Vitest
needs explicit `import { describe, it, expect } from 'vitest'` unless globals are enabled.

- Match the existing suffix: `.test.ts` vs `.spec.ts`. Do not introduce a second.
- Assert on behavior, not implementation details.
- Fake timers for anything time-dependent; never `setTimeout` in a test to "wait".
