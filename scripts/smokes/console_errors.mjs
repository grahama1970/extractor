#!/usr/bin/env node
// Delegates to the canonical CDP console error smoke in scenarios/ux.
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const root = path.resolve(__dirname, '..', '..');
const delegate = path.join(root, 'scenarios', 'ux', 'console_errors.mjs');
const require = createRequire(import.meta.url);
await import(require.resolve(delegate));
