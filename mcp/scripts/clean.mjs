#!/usr/bin/env node

import { rmSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const mcpDir = resolve(dirname(fileURLToPath(import.meta.url)), '..');
rmSync(resolve(mcpDir, 'dist'), { recursive: true, force: true });
