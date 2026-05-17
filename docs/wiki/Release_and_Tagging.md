# Release and Tagging

This project has a public tag history through `v1.6.4`. The current working tree is clean post-v1.6.4 with test suite expansion (1200 tests, 81% coverage).

## Current Rule

- Code first
- `CHANGELOG.md` second
- README/docs third
- Real-vault smoke check fourth
- Git tag last

Do not create a release tag before all five are aligned.

## Suggested Tag Strategy

Use semantic versioning:

- `v1.6.x` for retrieval improvements, bug fixes, docs, and operational hardening
- `v1.7.0` only if the public API or major operating model changes materially
- `v2.0.0` only for a breaking architecture shift

## Recommended Release Flow

1. Add user-visible changes to `CHANGELOG.md` under `Unreleased`
2. Update README examples and documentation links
3. Add or update focused docs in `docs/wiki/`
4. Run targeted tests
5. Run real-vault probe on the designated validation folder
6. Cut the release tag only after the above are green

## Candidate Next Tag

The current working tree is ready to tag as:

`v1.6.5`

Reason:

- Test suite expansion: 10 new test files, coverage 73.57% → 81%
- 1200 tests pass, 20 skipped
- No public API or behavior change

## Tag Hygiene

- Use annotated tags
- Keep `CHANGELOG.md` synchronized with tag contents
- Never move an existing published tag
- Do not tag from a dirty worktree unless the release commit is intentional and reviewable

Example:

```bash
git tag -a v1.6.5 -m "tests: v1.6.5 test suite expansion, coverage 73% -> 81%"
git push origin v1.6.5
```

## Release Checklist

- `CHANGELOG.md` updated
- `README.md` updated
- docs hub valid and linked
- probe report stored in `data/`
- tests green
- version bump decided
- tag message written
