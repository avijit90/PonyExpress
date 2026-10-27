from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from .core import CapsuleError, assemble, publish, receive_chunk, verify_capsule


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="ponyexpress", description="Verified Git capsule transport")
    commands = root.add_subparsers(dest="command", required=True)

    create = commands.add_parser("publish", help="Create a verified full capsule from an upstream Git URL")
    create.add_argument("--source-url", required=True)
    create.add_argument("--ref", default="HEAD")
    create.add_argument("--capsule-root", type=Path, required=True, help="Checked-out capsule repository")
    create.add_argument("--chunk-size", type=int, default=512 * 1024)
    create.add_argument("--project-id")

    check = commands.add_parser("verify", help="Verify every chunk and the reconstructed bundle hash")
    check.add_argument("--manifest", type=Path, required=True)
    check.add_argument("--chunk-root", type=Path, required=True)

    receive = commands.add_parser("receive-chunk", help="Validate then atomically cache one browser-retrieved chunk")
    receive.add_argument("--manifest", type=Path, required=True)
    receive.add_argument("--cache-root", type=Path, required=True)
    receive.add_argument("--index", type=int, required=True)
    receive.add_argument("--input", type=Path, required=True)

    unpack = commands.add_parser("assemble", help="Verify a complete cache and clone the resulting Git bundle")
    unpack.add_argument("--manifest", type=Path, required=True)
    unpack.add_argument("--cache-root", type=Path, required=True)
    unpack.add_argument("--output", type=Path, required=True)
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "publish":
            print(publish(args.source_url, args.ref, args.capsule_root, args.chunk_size, args.project_id))
        elif args.command == "verify":
            manifest = verify_capsule(args.manifest, args.chunk_root)
            print(f"verified {manifest['project_id']} {manifest['source']['commit']}")
        elif args.command == "receive-chunk":
            print(receive_chunk(args.manifest, args.cache_root, args.index, args.input))
        elif args.command == "assemble":
            assemble(args.manifest, args.cache_root, args.output)
            print(args.output)
    except (CapsuleError, subprocess.CalledProcessError) as exc:
        print(f"ponyexpress: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
