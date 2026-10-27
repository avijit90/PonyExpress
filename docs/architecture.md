# Architecture

## Lifecycle

```text
upstream URL → temporary mirror clone → Git bundle → checked chunks + manifest
             → destination capsule repository → browser reader → checked cache
             → Git bundle → normal local Git checkout
```

The capsule repository is a transport repository. It is not a fork and it does not contain a worktree copy of the upstream project.

## Capsule layout

```text
capsules/<project-id>/
  latest.json
  versions/<version>/
    manifest.json
    chunks/000000.b64
    chunks/000001.b64
```

Chunk files are Base64 text, wrapped at 76 columns so GitHub and GitLab code views can display them predictably. The default decoded chunk size is 512 KiB; providers may choose a smaller size when their browser viewer has a lower render limit.

## Provider boundary

A browser provider retrieves a manifest and chunk text from ordinary GitHub/GitLab file pages using the existing authenticated browser session. It must not decide integrity. Its only output is the bytes supplied to the receive/cache gate.

## Updates

The next milestone adds incremental bundles. A delta manifest will declare `bundle.kind: delta`, a `base_commit`, and a target ref/commit. The assembler must verify that the local checkout contains that exact base commit before fetching the bundle. Otherwise it requests a full capsule.

Git LFS payloads and submodule content require their own capsules; Git bundles contain LFS pointers and submodule gitlinks, not their external object stores.
