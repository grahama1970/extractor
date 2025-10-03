// Thin wrapper to the root-level ux_cdp_health script for consistency
import path from 'node:path';
import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
await import(require.resolve(path.resolve('scenarios/ux_cdp_health.mjs')));

