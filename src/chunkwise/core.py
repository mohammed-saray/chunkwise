"""Collect files and pack them into token-budgeted parts with a paste protocol."""
from __future__ import annotations

import fnmatch
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

from .tokens import estimate

DEFAULT_IGNORES = [".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build", ".next", "target",
                   ".idea", ".vscode", "*.lock", "package-lock.json", "*.min.js", "*.map", "*.pyc", ".DS_Store",
                   "*.png", "*.jpg", "*.jpeg", "*.gif", "*.webp", "*.ico", "*.pdf", "*.zip", "*.gz", "*.exe",
                   "*.dll", "*.so", "*.woff", "*.woff2", "*.ttf", "*.mp4", "*.mp3"]
LANG = {".py": "python", ".js": "javascript", ".ts": "typescript", ".tsx": "tsx", ".jsx": "jsx", ".go": "go",
        ".rs": "rust", ".java": "java", ".kt": "kotlin", ".c": "c", ".h": "c", ".cpp": "cpp", ".cs": "csharp",
        ".rb": "ruby", ".php": "php", ".sh": "bash", ".ps1": "powershell", ".md": "markdown", ".json": "json",
        ".yml": "yaml", ".yaml": "yaml", ".toml": "toml", ".html": "html", ".css": "css", ".sql": "sql",
        ".ino": "cpp", ".swift": "swift"}
BOUNDARY = re.compile(r"^(def |class |async def |function |export |const \w+ = |func |fn |pub |impl |"
                      r"public |private |protected |interface |type |#{1,3} |@\w+)")


@dataclass
class Piece:
    path: str
    text: str
    start: int
    end: int
    part: int = 1
    parts: int = 1

    @property
    def label(self) -> str:
        if self.parts == 1:
            return self.path
        return f"{self.path} (part {self.part}/{self.parts}, lines {self.start}-{self.end})"


@dataclass
class Chunk:
    pieces: List[Piece] = field(default_factory=list)
    tokens: int = 0


def load_gitignore(root: Path) -> List[str]:
    gi = root / ".gitignore"
    if not gi.is_file():
        return []
    pats = []
    for line in gi.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if line and not line.startswith(("#", "!")):
            pats.append(line.rstrip("/").lstrip("/"))
    return pats


def ignored(rel: str, patterns: Iterable[str]) -> bool:
    parts = rel.split("/")
    for pat in patterns:
        if "/" in pat:
            if fnmatch.fnmatch(rel, pat) or rel.startswith(pat + "/"):
                return True
        elif any(fnmatch.fnmatch(p, pat) for p in parts):
            return True
    return False


def is_binary(path: Path) -> bool:
    try:
        with open(path, "rb") as fh:
            return b"\0" in fh.read(4096)
    except OSError:
        return True


def collect(inputs: List[str], include: List[str], exclude: List[str], max_file_kb: int = 1024) -> List[Tuple[str, str]]:
    files: List[Tuple[str, str]] = []
    for inp in inputs:
        p = Path(inp)
        if p.is_file():
            files.append((p.as_posix(), p.read_text(encoding="utf-8", errors="replace")))
            continue
        if not p.is_dir():
            raise FileNotFoundError(inp)
        patterns = DEFAULT_IGNORES + load_gitignore(p) + exclude
        for f in sorted(p.rglob("*")):
            if not f.is_file():
                continue
            rel = f.relative_to(p).as_posix()
            if ignored(rel, patterns):
                continue
            if include and not any(fnmatch.fnmatch(rel, i) or fnmatch.fnmatch(f.name, i) for i in include):
                continue
            if f.stat().st_size > max_file_kb * 1024 or is_binary(f):
                continue
            files.append(((p.name + "/" + rel) if p.name else rel, f.read_text(encoding="utf-8", errors="replace")))
    return files


def split_text(path: str, text: str, budget: int, overlap: int = 0) -> List[Piece]:
    """Split one file into pieces under `budget` tokens, preferring natural boundaries."""
    if estimate(text) <= budget:
        n = text.count("\n") + 1
        return [Piece(path, text, 1, n)]
    lines = text.split("\n")
    pieces: List[Piece] = []
    start = 0
    while start < len(lines):
        end, tokens, best = start, 0, None
        while end < len(lines):
            t = estimate(lines[end] + "\n")
            if tokens + t > budget and end > start:
                break
            tokens += t
            end += 1
            if end < len(lines) and (BOUNDARY.match(lines[end]) or not lines[end - 1].strip()):
                best = end
        if end < len(lines) and best and best > start + (end - start) // 2:
            end = best  # cut at a definition/heading/blank line in the second half of the window
        pieces.append(Piece(path, "\n".join(lines[start:end]), start + 1, end))
        if end >= len(lines):
            break
        start = max(end - overlap, start + 1)
    for i, pc in enumerate(pieces, 1):
        pc.part, pc.parts = i, len(pieces)
    return pieces


def overhead(piece: Piece) -> int:
    return estimate(f"### {piece.label}\n```{LANG.get(Path(piece.path).suffix, '')}\n\n```\n") + 2


def pack(files: List[Tuple[str, str]], budget: int, overlap: int = 0, reserve: int = 250) -> List[Chunk]:
    """Greedy packing in file order (keeps related files together)."""
    room = max(budget - reserve, 200)
    pieces: List[Piece] = []
    for path, text in files:
        pieces += split_text(path, text, room - 40, overlap)
    chunks: List[Chunk] = [Chunk()]
    for pc in pieces:
        cost = estimate(pc.text) + overhead(pc)
        if chunks[-1].pieces and chunks[-1].tokens + cost > room:
            chunks.append(Chunk())
        chunks[-1].pieces.append(pc)
        chunks[-1].tokens += cost
    return [c for c in chunks if c.pieces]


INTRO = ("I'm going to send you {n} parts of {what}. It doesn't fit in one message.\n"
         "Until I send the last part, reply ONLY with \"OK, part X/{n} received\" and nothing else. "
         "Don't summarize or answer yet.")
LAST = "This was the last part ({n}/{n}). You now have everything.\n\n{question}"
MIDDLE = "Part {i}/{n}. Reply only \"OK, part {i}/{n} received\"."


def render(chunks: List[Chunk], question: str, what: str = "some files", manifest: bool = True) -> List[str]:
    n = len(chunks)
    out = []
    for i, ch in enumerate(chunks, 1):
        body = []
        if i == 1 and n > 1:
            body.append(INTRO.format(n=n, what=what))
            if manifest:
                listing = sorted({p.path for c in chunks for p in c.pieces})
                body.append("Files included:\n" + "\n".join(f"- {f}" for f in listing[:200]))
        body.append(f"--- PART {i}/{n} ---")
        for pc in ch.pieces:
            body.append(f"### {pc.label}\n```{LANG.get(Path(pc.path).suffix, '')}\n{pc.text}\n```")
        if i == n:
            body.append(LAST.format(n=n, question=question) if n > 1 else question)
        elif i > 1:
            body.append(MIDDLE.format(i=i, n=n))
        out.append("\n\n".join(body))
    return out


def preset_budget(name: Optional[str]) -> Optional[int]:
    """Conservative per-message budgets for pasting into web chats (well under the real limits)."""
    return {"chatgpt": 12000, "claude": 40000, "gemini": 60000, "small": 4000}.get((name or "").lower())
