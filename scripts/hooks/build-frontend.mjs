#!/usr/bin/env node
/**
 * Stop hook — runs the real frontend build once a turn has finished, but only
 * when frontend sources are newer than the last build output.
 *
 * This is the honest end-of-turn check: `npm run build` is `tsc -b && vite
 * build`, so a green result means the app actually compiles.
 *
 * Exit codes
 *   0  nothing changed, build skipped, or the build passed
 *   2  build failed — stderr is fed back to Claude so it can fix it
 *
 * Guards against looping via `stop_hook_active`, and never runs when the
 * toolchain is missing. It writes only to `frontend/dist`, which is the normal
 * build output and is git-ignored.
 */
import { spawnSync } from 'node:child_process';
import { existsSync, statSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { newestMtime, npmCommand, readStdinJson } from './_lib.mjs';

const projectRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
const frontendDir = join(projectRoot, 'frontend');

const payload = await readStdinJson();

// Claude is already responding to this hook — do not ask it to build again.
if (payload?.stop_hook_active) process.exit(0);

if (!existsSync(join(frontendDir, 'node_modules'))) {
  console.error('[build-frontend] skipped: frontend dependencies not installed.');
  process.exit(0);
}

// Skip when nothing under frontend/ changed since the last successful build.
const marker = join(frontendDir, 'dist', 'index.html');
if (existsSync(marker)) {
  let builtAt = 0;
  try {
    builtAt = statSync(marker).mtimeMs;
  } catch {
    builtAt = 0;
  }
  if (builtAt > 0 && newestMtime(frontendDir) <= builtAt) process.exit(0);
}

const result = spawnSync(npmCommand(), ['run', 'build'], {
  cwd: frontendDir,
  encoding: 'utf8',
  shell: process.platform === 'win32',
});

if (result.error) {
  console.error(`[build-frontend] could not run npm: ${result.error.message}`);
  process.exit(0);
}

if (result.status !== 0) {
  const output = `${result.stdout ?? ''}${result.stderr ?? ''}`.trim();
  console.error(
    'The frontend build is failing — fix it before finishing:\n\n' +
      (output || 'npm run build exited non-zero with no output.'),
  );
  process.exit(2);
}

process.exit(0);
