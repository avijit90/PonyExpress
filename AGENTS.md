# PonyExpress agent guide

## Mission

PonyExpress transports an allowed upstream Git repository through a browser-readable capsule while preserving an ordinary local Git repository at the destination.

## Integrity contract

Treat a capsule as untrusted until all of these hold:

1. Every encoded chunk matches its manifest SHA-256.
2. Every decoded chunk matches its byte count and SHA-256.
3. Concatenated decoded chunks match the bundle SHA-256 and byte count.
4. `git bundle verify` succeeds before a destination checkout is created or updated.

Preserve these gates in every new provider, update path, and optimization. Cache only chunks that have passed their per-chunk checks. Write cache files atomically.

## Boundaries

- `src/ponyexpress/core.py` is provider-neutral integrity and Git-bundle logic.
- Browser readers belong in a provider module. They may obtain text only; they must pass it through `receive_chunk` semantics before it enters the cache.
- CI workflows publish only generated capsule files. The cloned upstream repository is temporary and must remain unmodified by PonyExpress.
- A normal project checkout receives no PonyExpress metadata except standard `.git` state created by `git clone`/`git fetch`.

## Working rules

- Run `python -m unittest discover -s tests -v` after changes.
- Add a test for every accepted or rejected data-path change.
- Keep `manifest.json` backward-compatible; a format change requires a new `format_version` and migration/read policy.
- Publish `latest.json` only after validating the referenced version completely.
- Prefer full capsules over an unsafe incremental update. An incremental bundle must declare and verify its required base commit.

## References

- [Architecture](docs/architecture.md): lifecycle and future provider/update boundaries.
- [CI setup](docs/ci.md): GitHub Actions and GitLab CI examples.
