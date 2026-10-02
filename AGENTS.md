# Autonomous Agent Guidelines

## Autonomous Execution Rules
- **No Interactive Interruption**: Do not use interactive question tools (`ask_question`) or prompt the user for permission / options.
- **Autonomous Decision Making**: When there are multiple choices or design decisions, select the cleanest, most idiomatic, and best-practice solution autonomously and proceed.
- **End-to-End Delivery**: Complete the requested work thoroughly across all relevant files, verify correctness, and commit \
- **Direct & Action-Oriented**: Keep chat messages concise and focused on what was accomplished.

## Context hygiene (read first)
- `index.html`, `campaign.json` and `assets/*.js` are ~30 MB of mostly base64. **Never read them whole.** Read `DOCUMENTATION.md` instead — §18 is a line-numbered code map. Then `Grep -n` + `Read` with `offset`/`limit`.
- Keep `DOCUMENTATION.md` current: when you change behaviour or move code, update the relevant section and the §18 line numbers in the same commit.
- Pull (`git pull --rebase --autostash origin main`) before every commit and push — players commit turns to `main` constantly.
