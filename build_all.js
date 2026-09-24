import { execSync } from 'child_process';
import fs from 'fs';
import path from 'path';

console.log('====================================================');
console.log('  Building AAROGYA-SHIELD Unified Dist for Vercel  ');
console.log('====================================================');

// 1. Build user-ui (Smartwatch Companion)
console.log('[1/3] Building user-ui (Smartwatch Companion)...');
execSync('npm --prefix user-ui install && npm --prefix user-ui run build', { stdio: 'inherit' });

// 2. Build testing-ui (Simulation Lab)
console.log('[2/3] Building testing-ui (Simulation Lab)...');
execSync('npm --prefix testing-ui install && npm --prefix testing-ui run build', { stdio: 'inherit' });

// 3. Assemble Unified Dist Directory
console.log('[3/3] Assembling unified distribution directory...');
const distDir = path.resolve('dist');
if (fs.existsSync(distDir)) {
  fs.rmSync(distDir, { recursive: true, force: true });
}
fs.mkdirSync(distDir, { recursive: true });

// Root '/' serves user-ui (Smartwatch Companion)
const userDist = path.resolve('user-ui/dist');
fs.cpSync(userDist, distDir, { recursive: true });

// '/lab' serves testing-ui (Simulation Lab)
const testingDist = path.resolve('testing-ui/dist');
const labDir = path.join(distDir, 'lab');
fs.mkdirSync(labDir, { recursive: true });
fs.cpSync(testingDist, labDir, { recursive: true });

console.log('====================================================');
console.log('  Vercel Unified Build Complete!                     ');
console.log('  - Root (/) -> Smartwatch Companion                 ');
console.log('  - Subpath (/lab) -> Simulation Lab                 ');
console.log('====================================================');
