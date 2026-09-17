#!/usr/bin/env node
/**
 * PostToolUse hook — type-checks the frontend after a source edit.
 *
 * Runs only when the edited file is a TypeScript source under `frontend/src`.
 * Anything else exits immediately, so the hook is invisible for docs, CSS,
 * config and backend files.
 *
 * Exit codes
 *   0  nothing to do, or the type check passed
 *   2  type errors — stderr is fed back to Claude so it can fix them
 *
 * It never writes to the repository and never installs anything. If the
 * toolchain is missing it exits 0 with a note rather than blocking work.
 */
import { spawnSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import { dirname, join, resolve, sep } from 'node:path';
import { fileURLToPath } from 'node:url';
import { readStdinJson, tscBinary } from './_lib.mjs';

const projectRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
const frontendDir = join(projectRoot, 'frontend');

const payload = await readStdinJson();
const filePath = payload?.tool_input?.file_path ?? '';

// Only care about TypeScript sources inside the frontend app.
const watched = join(frontendDir, 'src') + sep;
const isFrontendSource =
  typeof filePath === 'string' &&
  resolve(filePath).startsWith(watched) &&
  /\.(ts|tsx)$/.test(filePath);

if (!isFrontendSource) process.exit(0);

const tsc = tscBinary(frontendDir);
if (!tsc || !existsSync(join(frontendDir, 'node_modules'))) {
  console.error('[typecheck-frontend] skipped: frontend dependencies not installed.');
  process.exit(0);
}

// `tsc -b` is incremental (tsBuildInfoFile is configured), so this is cheap.
const result = spawnSync(tsc, ['-b'], {
  cwd: frontendDir,
  encoding: 'utf8',
  shell: process.platform === 'win32',
});

if (result.error) {
  console.error(`[typecheck-frontend] could not run tsc: ${result.error.message}`);
  process.exit(0);
}

if (result.status !== 0) {
  const output = `${result.stdout ?? ''}${result.stderr ?? ''}`.trim();
  console.error(
    'TypeScript errors in frontend/ — fix these before continuing:\n\n' +
      (output || 'tsc exited non-zero with no output.'),
  );
  process.exit(2);
}

process.exit(0);
