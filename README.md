# chunkwise 🧩

**"Message too long." "Conversation is too long." chunkwise splits files and whole folders into parts that fit, with a paste protocol so ChatGPT, Claude or Gemini waits for the last part before it answers.**

[![CI](https://github.com/mohammed2345353/chunkwise/actions/workflows/ci.yml/badge.svg)](https://github.com/mohammed2345353/chunkwise/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.9%2B-blue)
![Dependencies](https://img.shields.io/badge/dependencies-0-brightgreen)
[![License: MIT](https://img.shields.io/badge/license-MIT-yellow.svg)](LICENSE)

```text
$ chunkwise ./my-app --for chatgpt -q "Find the bug that makes login fail after a refresh."
chunkwise: 46 file(s), ≈41,280 tokens → 4 part(s) of ≤12,000 tokens (heuristic (≈ chars/4))
✓ wrote 4 part(s) to chunks/ — paste them in order.

$ chunkwise ./my-app --plan -t 3000
part   1: ≈ 2,418 tokens  my-app/README.md, my-app/package.json, my-app/src/api.ts … +3
part   2: ≈ 2,328 tokens  my-app/src/auth/session.ts
part   3: ≈ 2,589 tokens  my-app/src/auth/login.ts (part 1/2, lines 1-212)
part   4: ≈ 1,536 tokens  my-app/src/auth/login.ts (part 2/2, lines 213-340)
```

## The problem

Web chats limit how much you can paste in one message, and free tiers limit it
even more. Files over the upload limit get cut, and long pastes eat your message
quota. Splitting by hand breaks functions in half, and the assistant starts
answering after part 1 of 5.

chunkwise:

- **Packs whole files together** until the budget is reached, so related files stay in the same message.
- **Splits big files at natural boundaries**: function/class definitions, Markdown headings, blank lines. Each part is labeled `file.py (part 2/3, lines 120-240)`.
- **Adds a paste protocol.** Part 1 says "reply only *OK, part X/N received*", lists every file included, and the last part asks your question.
- Respects `.gitignore` and skips binaries, lockfiles, `node_modules`, build output and media.

## Install

```bash
pipx install git+https://github.com/mohammed2345353/chunkwise
```

## Usage

```bash
chunkwise src/ -q "Explain the architecture"         # writes chunks/part-001.md, part-002.md …
chunkwise big.log --for claude                       # preset budgets: chatgpt, claude, gemini, small
chunkwise . -t 6000 --include "*.py" --exclude "tests/*"
chunkwise notes.md --interactive                     # copies part 1, Enter → copies part 2, …
cat transcript.txt | chunkwise --stdout -t 4000      # from stdin
chunkwise . --plan                                   # preview only
```

| Option | Default | |
|---|---|---|
| `-t, --max-tokens` | 8000 | tokens per part |
| `--for` | — | `chatgpt` 12K · `claude` 40K · `gemini` 60K · `small` 4K (deliberately conservative) |
| `-q, --question` | — | asked in the last part |
| `-o, --out` | `chunks/` | output folder (old `part-*.md` files are replaced) |
| `--overlap` | 0 | lines repeated between parts of a split file |
| `--include` / `--exclude` | — | globs, repeatable |
| `--no-manifest` | — | don't list files in part 1 |

## Tips

- If you're sending a **whole repo**, try a model with a big context window first (for example Gemini in AI Studio) and use `--for gemini`.
- Shrink logs before chunking them: `logslim -t 20000 app.log | chunkwise --for chatgpt`.
- Coding agents (Claude Code, Codex, Gemini CLI) read files themselves. chunkwise is for **web chats** and APIs where you control the message.

## Limitations

- Token counts are estimates. The presets leave headroom, and `--max-tokens` lets you go lower.
- A single line longer than the budget (minified code) can't be split.
- `.gitignore` support covers common patterns (no `!` negation).

## Roadmap

- [ ] `--summary-first` to send a file tree + signatures before full code
- [ ] Split PDFs and DOCX via optional extras
- [ ] Browser extension that pastes parts automatically

## Related tools in this suite

Small, dependency-free tools for people fighting AI usage limits:

| Tool | What it does |
|---|---|
| [burnrate](https://github.com/mohammed2345353/burnrate) | Forecast Claude Code / Codex limits from local logs |
| [context-diet](https://github.com/mohammed2345353/context-diet) | Find the CLAUDE.md / AGENTS.md / GEMINI.md bloat you pay for on every message |
| [ai-handoff](https://github.com/mohammed2345353/ai-handoff) | Hit a limit? Move the task to another AI with a handoff file |
| [ai-error-decoder](https://github.com/mohammed2345353/ai-error-decoder) | Explain 429 / 529 / quota errors from Anthropic, OpenAI and Gemini |
| [ratelimit-retry](https://github.com/mohammed2345353/ratelimit-retry) | Retry that respects provider rate-limit headers (JS) |
| [chat-export-md](https://github.com/mohammed2345353/chat-export-md) | ChatGPT / Claude / Gemini exports → Markdown |
| [mcp-token-audit](https://github.com/mohammed2345353/mcp-token-audit) | Measure how many tokens each MCP server's tools cost |
| [logslim](https://github.com/mohammed2345353/logslim) | Shrink logs and stack traces before pasting them into a chat |
| **chunkwise** | Split big files into token-budgeted chunks with continuation prompts |
| [ai-reset-clock](https://github.com/mohammed2345353/ai-reset-clock) | When does my quota reset? A countdown in your timezone |

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE)
