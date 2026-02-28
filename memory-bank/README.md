# Memory Bank — openemr-agent

Persistent context for AI assistance in the **openemr-agent** microservice. Reference these files for service-specific awareness when working inside `openemr-agent/`.

## Files

| File | Purpose |
|------|---------|
| `projectContext.md` | Service overview, directory structure, tools, env vars, run/test commands |
| `activeContext.md` | Current focus, recent decisions, blockers |
| `architecture.md` | LangGraph design, DB persistence, auth, security, conventions |

## Usage

- **Update `activeContext.md`** when starting new work, adding tools, or changing priorities
- **Update `architecture.md`** when making significant design or infrastructure decisions
- **Update `projectContext.md`** when the directory layout, tools list, or setup steps change

## Cursor Integration

Reference these files with `@openemr-agent/memory-bank/` in Cursor chat, or use the `openemr-agent-navigation` skill for quick orientation.
