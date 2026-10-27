# PonyExpress

PonyExpress packages an upstream Git repository into a **verified, browser-readable capsule**. A publisher creates the capsule in a GitHub or GitLab destination repository; an assembler retrieves its text chunks through an allowed browser path, validates every byte, and produces a normal local Git checkout.

It is designed for people and coding agents. Read [AGENTS.md](AGENTS.md) before changing behavior; it defines the integrity contract.

## Two modes

| Mode | Runs where | Result |
| --- | --- | --- |
| `publish` | CI or an unrestricted machine | A capsule directory ready to commit to the destination GitHub/GitLab repository. |
| `receive-chunk` + `assemble` | Restricted machine | A verified, ordinary local Git checkout. |

The source repository is cloned only into a temporary publisher workspace. Transfer files, manifests, and checksums are never written into it.

## Quick start

Install from a checkout:

```bash
python3 -m pip install -e .
```

In CI, after checking out the capsule destination repository:

```bash
ponyexpress publish \
  --source-url https://gitlab.com/example/project.git \
  --ref main \
  --capsule-root "$GITHUB_WORKSPACE" \
  --project-id example-project
```

Commit and push the resulting `capsules/example-project/` directory. The first implementation intentionally makes **full** Git bundle capsules; full capsules preserve Git history, branches, tags, symlinks, executable permissions, and tree layout.

On the restricted machine, use the browser automation agent to retrieve `latest.json`, its referenced `manifest.json`, and each visible `chunks/*.b64` file. For each chunk, call:

```bash
ponyexpress receive-chunk \
  --manifest ./downloaded/manifest.json \
  --cache-root ~/.cache/ponyexpress/example-project \
  --index 0 \
  --input ./downloaded/000000.b64
```

`receive-chunk` only keeps chunks whose encoded and decoded checksums match. Once all chunks are cached:

```bash
ponyexpress assemble \
  --manifest ./downloaded/manifest.json \
  --cache-root ~/.cache/ponyexpress/example-project \
  --output ~/src/example-project
```

## Integrity model

The manifest holds the SHA-256 and decoded byte count of every chunk plus the SHA-256 and byte count of the complete Git bundle. Publisher and assembler both rebuild and verify the bundle. The publisher also runs `git bundle verify`; the assembler verifies before producing a checkout.

`latest.json` is a pointer written only after the complete version validates. CI should commit a generated version and its new `latest.json` in one commit.

## Current scope

PonyExpress has a tested full-capsule path and a validated receive/cache boundary. The GitHub/GitLab browser readers and incremental bundles are intentionally separate next steps: UI-specific selectors must not be mixed with the bundle integrity core.

See [docs/architecture.md](docs/architecture.md) for the intended complete flow and [docs/ci.md](docs/ci.md) for CI setup.
