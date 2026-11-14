"""chunkwise command-line interface."""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

from . import __version__
from .core import collect, pack, preset_budget, render
from .tokens import estimate, method


def _copy(text: str) -> bool:
    for cmd in (["clip"], ["pbcopy"], ["wl-copy"], ["xclip", "-selection", "clipboard"]):
        if shutil.which(cmd[0]):
            try:
                subprocess.run(cmd, input=text.encode("utf-16le" if cmd[0] == "clip" else "utf-8"), check=True)
                return True
            except (OSError, subprocess.SubprocessError):
                pass
    return False


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="chunkwise", description="Split files or folders into token-budgeted "
                                 "parts you can paste one by one into ChatGPT, Claude or Gemini.")
    ap.add_argument("inputs", nargs="*", help="files and/or folders (default: stdin)")
    ap.add_argument("-t", "--max-tokens", type=int, help="tokens per part (default 8000)")
    ap.add_argument("--for", dest="preset", choices=["chatgpt", "claude", "gemini", "small"],
                    help="conservative per-message budget for that web chat")
    ap.add_argument("-q", "--question", default="Now answer my question about all of it: ",
                    help="what to ask once everything is sent")
    ap.add_argument("-o", "--out", default="chunks", help="output folder (default ./chunks)")
    ap.add_argument("--stdout", action="store_true", help="print parts separated by a line of '='")
    ap.add_argument("--interactive", "-i", action="store_true", help="copy each part to the clipboard, press Enter for the next")
    ap.add_argument("--include", action="append", default=[], help="glob to include (repeatable), e.g. '*.py'")
    ap.add_argument("--exclude", action="append", default=[], help="glob to exclude (repeatable)")
    ap.add_argument("--overlap", type=int, default=0, help="lines repeated between parts of a split file")
    ap.add_argument("--no-manifest", action="store_true", help="don't list files in the first part")
    ap.add_argument("--plan", action="store_true", help="only show how it would split")
    ap.add_argument("--version", action="version", version=f"chunkwise {__version__}")
    a = ap.parse_args(argv)
    for s in (sys.stdout, sys.stderr):
        if hasattr(s, "reconfigure"):
            try:
                s.reconfigure(encoding="utf-8")
            except Exception:
                pass

    budget = a.max_tokens or preset_budget(a.preset) or 8000
    if a.inputs:
        files = collect(a.inputs, a.include, a.exclude)
        what = "a codebase" if any(Path(i).is_dir() for i in a.inputs) else \
            ("a file" if len(files) == 1 else f"{len(files)} files")
    else:
        files = [("stdin.txt", sys.stdin.read())]
        what = "a long text"
    if not files:
        print("chunkwise: nothing to split (all files ignored?)", file=sys.stderr)
        return 1
    chunks = pack(files, budget, a.overlap)
    parts = render(chunks, a.question, what, manifest=not a.no_manifest)
    total = sum(estimate(t) for _, t in files)
    print(f"chunkwise: {len(files)} file(s), ≈{total:,} tokens → {len(parts)} part(s) of ≤{budget:,} tokens "
          f"({method()})", file=sys.stderr)

    if a.plan:
        for i, ch in enumerate(chunks, 1):
            print(f"part {i:>3}: ≈{ch.tokens:>6,} tokens  " + ", ".join(p.label for p in ch.pieces[:6])
                  + (f" … +{len(ch.pieces) - 6}" if len(ch.pieces) > 6 else ""))
        return 0
    if a.stdout:
        print(("\n\n" + "=" * 72 + "\n\n").join(parts))
        return 0
    if a.interactive:
        for i, part in enumerate(parts, 1):
            ok = _copy(part)
            msg = f"[{i}/{len(parts)}] {'copied — paste it, then' if ok else 'no clipboard tool; printing. Then'} press Enter"
            if not ok:
                print(part)
            try:
                input(msg + (" for the next part…" if i < len(parts) else " to finish."))
            except (EOFError, KeyboardInterrupt):
                print()
                return 0
        return 0
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("part-*.md"):
        old.unlink()
    width = max(3, len(str(len(parts))))
    for i, part in enumerate(parts, 1):
        (out / f"part-{i:0{width}d}.md").write_text(part, encoding="utf-8", newline="\n")
    print(f"✓ wrote {len(parts)} part(s) to {out.as_posix()}/ — paste them in order.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
