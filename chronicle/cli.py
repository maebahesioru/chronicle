"""Command line entry point for Chronicle."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys

from . import __version__
from .build import BuildError, BuildOptions, build
from .core.cluster import DEFAULT_MAX_COMMITS, DEFAULT_SIMILARITY
from .i18n import LANGS, normalize_lang


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="chronicle",
        description="Chronicle - hear why your code exists. Turns a git history into narrated, cited chapters.",
    )
    parser.add_argument("--version", action="version", version="chronicle " + __version__)
    sub = parser.add_subparsers(dest="command")

    build_cmd = sub.add_parser("build", help="read a git repository and write a narrated chapter folder")
    build_cmd.add_argument("--repo", default=".", help="path to the git repository (default: .)")
    build_cmd.add_argument("--since", default=None, help="only commits after this ref/tag (release mode)")
    build_cmd.add_argument("--out", default="chronicle-out", help="output folder (default: chronicle-out)")
    build_cmd.add_argument(
        "--lang",
        default="en",
        choices=list(LANGS),
        help="narration language (default: en)",
    )
    build_cmd.add_argument(
        "--similarity",
        type=float,
        default=DEFAULT_SIMILARITY,
        help="file-overlap threshold for clustering non-conventional commits (default: %.2f)" % DEFAULT_SIMILARITY,
    )
    build_cmd.add_argument(
        "--max-commits",
        type=int,
        default=DEFAULT_MAX_COMMITS,
        help="maximum commits per chapter (default: %d)" % DEFAULT_MAX_COMMITS,
    )
    build_cmd.add_argument("--no-audio", action="store_true", help="skip edge-tts and write a text-only player")
    build_cmd.add_argument("--no-llm", action="store_true", help="force the deterministic summary engine")
    build_cmd.add_argument("--json", action="store_true", help="print the build report as JSON")
    build_cmd.add_argument("-q", "--quiet", action="store_true", help="suppress progress lines on stderr")

    doctor = sub.add_parser("doctor", help="report which optional pieces are available")
    doctor.add_argument("--lang", default="en", choices=list(LANGS))
    return parser


def cmd_build(args) -> int:
    lang = normalize_lang(args.lang)
    if args.similarity < 0 or args.similarity > 1:
        print("error: --similarity must be between 0 and 1", file=sys.stderr)
        return 2
    if args.max_commits < 1:
        print("error: --max-commits must be at least 1", file=sys.stderr)
        return 2

    def log(message: str) -> None:
        if not args.quiet:
            print("  " + message, file=sys.stderr)

    options = BuildOptions(
        repo=args.repo,
        since=args.since,
        out=args.out,
        lang=lang,
        similarity=args.similarity,
        max_commits=args.max_commits,
        audio=not args.no_audio,
        llm=not args.no_llm,
    )
    try:
        report = build(options, log=log)
    except BuildError as exc:
        print("chronicle: " + str(exc), file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("chronicle: interrupted", file=sys.stderr)
        return 130

    if args.json:
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    else:
        for line in report.summary_lines():
            print(line)
    return 0


def cmd_doctor(args) -> int:
    from .audio import edge_tts_available, voice_for
    from .core.gitlog import is_git_repo
    from .llm import config_from_env

    lang = normalize_lang(args.lang)
    config = config_from_env()
    checks = [
        ("python", sys.version.split()[0]),
        ("git", shutil.which("git") or "missing"),
        ("ffprobe", shutil.which("ffprobe") or "optional, missing"),
        ("edge-tts", ("available, voice " + voice_for(lang)) if edge_tts_available() else "not installed (silent fallback)"),
        ("llm backend", config.backend + (" (key set)" if config.api_key else " (no key: deterministic)")),
        ("llm base url", config.base_url),
        ("llm model", config.model),
        ("cwd is git repo", "yes" if is_git_repo(os.getcwd()) else "no"),
    ]
    width = max(len(name) for name, _ in checks)
    for name, value in checks:
        print(name.ljust(width) + "  " + value)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "command", None):
        parser.print_help()
        return 2
    if args.command == "build":
        return cmd_build(args)
    if args.command == "doctor":
        return cmd_doctor(args)
    parser.print_help()
    return 2
