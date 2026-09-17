/**
 * Shared helpers for the Cybrain QS hook scripts.
 * Read-only, no side effects on the repository.
 */
import { existsSync, readdirSync, statSync } from 'node:fs';
import { join } from 'node:path';

/** Read the hook payload from stdin. Returns `{}` if there is nothing to read. */
export async function readStdinJson() {
  if (process.stdin.isTTY) return {};
  let raw = '';
  try {
    for await (const chunk of process.stdin) raw += chunk;
    return raw.trim() ? JSON.parse(raw) : {};
  } catch {
    return {};
  }
}

/** Resolve the locally installed tsc binary, or null when it is missing. */
export function tscBinary(frontendDir) {
  const base = join(frontendDir, 'node_modules', '.bin', 'tsc');
  for (const candidate of process.platform === 'win32' ? [`${base}.cmd`, base] : [base]) {
    if (existsSync(candidate)) return candidate;
  }
  return null;
}

/** Resolve the npm executable name for the current platform. */
export function npmCommand() {
  return process.platform === 'win32' ? 'npm.cmd' : 'npm';
}

/** Most recent mtime under `dir`, skipping the given directory names. */
export function newestMtime(dir, skip = new Set(['node_modules', 'dist', '.git'])) {
  let newest = 0;
  const walk = (current) => {
    let entries;
    try {
      entries = readdirSync(current, { withFileTypes: true });
    } catch {
      return;
    }
    for (const entry of entries) {
      if (skip.has(entry.name)) continue;
      const full = join(current, entry.name);
      if (entry.isDirectory()) {
        walk(full);
      } else {
        try {
          newest = Math.max(newest, statSync(full).mtimeMs);
        } catch {
          /* file vanished mid-walk — ignore */
        }
      }
    }
  };
  walk(dir);
  return newest;
}
