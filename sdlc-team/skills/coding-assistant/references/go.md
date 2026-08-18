# Go conventions

> Verify against `go.mod` before applying. Check the declared Go version before using
> newer language or stdlib features.

## Detect first

```bash
head -5 go.mod
ls -1 .golangci.yml .golangci.yaml 2>/dev/null
find . -name '*_test.go' | head -10
```

## Style

- `gofmt` is not negotiable; run it. If `.golangci.yml` exists, satisfy it.
- Short receiver names (`func (s *Server)`), consistent across all methods on a type.
- Accept interfaces, return structs.
- Define interfaces in the *consuming* package, not alongside the implementation.

## Errors

- Return errors; do not panic in library code.
- Wrap with context: `fmt.Errorf("fetching user %s: %w", id, err)`.
- Check with `errors.Is` / `errors.As`, never string comparison.
- Sentinel errors as package-level `ErrFoo = errors.New(...)`.

## Structure

- Package name matches the directory; avoid `util`, `common`, `helpers`.
- `internal/` for anything not meant to be imported externally.
- Keep `main` thin — wire dependencies and delegate.

## Concurrency

- The goroutine's creator is responsible for its termination.
- Pass `context.Context` as the first parameter on anything that blocks.
- Guard shared state with a mutex, or avoid sharing via channels — do not do both halfway.

## Testing

- Table-driven tests are the default idiom.
- `t.Parallel()` where tests are independent.
- `t.Helper()` in assertion helpers so failures report the caller's line.
- Prefer the stdlib `testing` package unless the repo already uses `testify`.
