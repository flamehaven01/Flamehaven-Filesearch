# Release and Tagging

This project already has a public tag history through `v1.6.2`.

The current Obsidian-light and exact-note work is not tagged yet. Treat it as `Unreleased` until release notes, docs, and smoke validation are complete.

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

If the current working tree is released after review, the most natural next tag is:

`v1.6.3`

Reason:

- Search quality changed materially
- Obsidian light mode is now documented and operational
- No public breaking API change has been introduced

## Tag Hygiene

- Use annotated tags
- Keep `CHANGELOG.md` synchronized with tag contents
- Never move an existing published tag
- Do not tag from a dirty worktree unless the release commit is intentional and reviewable

Example:

```bash
git tag -a v1.6.3 -m "release: v1.6.3 obsidian light retrieval hardening"
git push origin v1.6.3
```

## Release Checklist

- `CHANGELOG.md` updated
- `README.md` updated
- docs hub valid and linked
- probe report stored in `data/`
- tests green
- version bump decided
- tag message written
