# Hooks

Validation hooks for the current **Frontend UI Development** phase. Wired in
[`.claude/settings.json`](../../.claude/settings.json).

They are deliberately conservative: they run read-only checks, never modify the
repository, never install anything, and never touch `frontend/src` or
`backend/`. The only thing either writes is `frontend/dist`, which is the normal
build output and is git-ignored.

| Script | Event | What it does |
| --- | --- | --- |
| `typecheck-frontend.mjs` | `PostToolUse` on `Write`/`Edit` | Runs `tsc -b` in `frontend/`, but only when the edited file is a `.ts`/`.tsx` file under `frontend/src`. Any other file exits instantly. |
| `build-frontend.mjs` | `Stop` | Runs `npm run build` in `frontend/`, but only when something under `frontend/` is newer than `frontend/dist/index.html`. |

`_lib.mjs` holds shared helpers (stdin parsing, binary resolution, mtime walk).

## Exit codes

- `0` — nothing to do, or the check passed.
- `2` — the check failed. stderr is fed back to Claude so it fixes the problem
  before continuing.

Any other outcome (missing `node_modules`, missing toolchain, npm not runnable)
exits `0` with a note on stderr. A broken environment should not block work.

## Loop safety

`build-frontend.mjs` exits immediately when the hook payload sets
`stop_hook_active`, so a failing build cannot trap Claude in a build-fix-build
cycle.

## Why Node and not shell

The project targets Windows with PowerShell as the primary shell, while Git Bash
is also present. Node is guaranteed available because the frontend needs it, and
one `.mjs` file behaves identically under both — no `.sh`/`.ps1` pair to keep in
sync.

Hook commands use paths relative to the project root, which is the working
directory Claude Code runs hooks from. No environment-variable expansion is
required, so the same command string works on every platform.

## Running them by hand

```bash
echo '{"tool_input":{"file_path":"frontend/src/App.tsx"}}' | node scripts/hooks/typecheck-frontend.mjs
echo '{}' | node scripts/hooks/build-frontend.mjs
```

## Changing them

Keep them deterministic and non-destructive. Do not add hooks that reformat,
auto-commit, auto-fix, delete files, or run network commands. If a future phase
needs backend or database validation, add a new script with the same shape and
the same exit-code contract.
