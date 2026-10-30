/**
 * Régénère les aperçus README + sync architecture (même commit docs que
 * Finalise / /msa — aucun bot GitHub Actions).
 *
 * 1. sync Mermaid architecture → README
 * 2. capture #travail-realise (HTML suivi, file://)
 * 3. build + serve docs-site → aperçus accueil et bugs
 *
 * Soft-skip (exit 0) si Playwright / build / serve manquent : un message
 * `[apercus-readme] soft-skip : …` ; le reste du commit docs continue.
 *
 * Usage : node docs-site/scripts/capturer-apercus-readme.mjs
 *     ou : npm run capturer-apercus-readme  (depuis docs-site/)
 */
import {spawn} from 'node:child_process';
import fs from 'node:fs';
import {createRequire} from 'node:module';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

const require = createRequire(import.meta.url);
const __dirname = path.dirname(fileURLToPath(import.meta.url));
const DOCS_SITE = path.resolve(__dirname, '..');
const PORT = 4173;
const BASE = `http://127.0.0.1:${PORT}/BBASS-Agents-IA/`;

function runNode(scriptRel, args = []) {
  return new Promise((resolve, reject) => {
    const child = spawn(
      process.execPath,
      [path.join(DOCS_SITE, 'scripts', scriptRel), ...args],
      {cwd: DOCS_SITE, env: process.env, stdio: 'inherit'},
    );
    child.on('error', reject);
    child.on('exit', (code) => {
      if (code === 0) resolve();
      else reject(new Error(`${scriptRel} exit ${code}`));
    });
  });
}

function softSkip(raison) {
  console.warn(`[apercus-readme] soft-skip : ${raison}`);
  process.exit(0);
}

async function waitReady(url, tries = 90) {
  for (let i = 0; i < tries; i++) {
    try {
      const res = await fetch(url);
      if (res.ok) return;
    } catch {
      /* pas encore prêt */
    }
    await new Promise((r) => setTimeout(r, 1000));
  }
  throw new Error(`serveur docs inaccessible : ${url}`);
}

function npmRunBuild() {
  return new Promise((resolve, reject) => {
    const child = spawn(
      process.platform === 'win32' ? 'npm.cmd' : 'npm',
      ['run', 'build'],
      {
        cwd: DOCS_SITE,
        env: process.env,
        stdio: 'inherit',
        shell: process.platform === 'win32',
      },
    );
    child.on('error', reject);
    child.on('exit', (code) => {
      if (code === 0) resolve();
      else reject(new Error(`npm run build exit ${code}`));
    });
  });
}

async function main() {
  try {
    require.resolve('playwright');
  } catch {
    softSkip('playwright introuvable : lancer `npm install` dans docs-site/');
  }

  try {
    await runNode('sync-architecture-readme.mjs');
    await runNode('capturer-travail-realise.mjs');
  } catch (err) {
    softSkip(err.message || String(err));
  }

  console.log('[apercus-readme] build docs-site…');
  try {
    await npmRunBuild();
  } catch (err) {
    softSkip(err.message || String(err));
  }

  const buildDir = path.join(DOCS_SITE, 'build');
  if (!fs.existsSync(buildDir)) {
    softSkip('docs-site/build absent après build');
  }

  const serve = spawn(
    process.execPath,
    [
      path.join(DOCS_SITE, 'node_modules/@docusaurus/core/bin/docusaurus.mjs'),
      'serve',
      '--host',
      '127.0.0.1',
      '--port',
      String(PORT),
    ],
    {cwd: DOCS_SITE, stdio: 'ignore', env: process.env},
  );

  try {
    await waitReady(BASE);
    await runNode('capturer-accueil.mjs', [BASE]);
    await runNode('capturer-bugs.mjs', [BASE]);
  } catch (err) {
    softSkip(err.message || String(err));
  } finally {
    serve.kill('SIGTERM');
  }

  console.log('[apercus-readme] aperçus README à jour');
}

main().catch((err) => {
  console.error('[apercus-readme]', err);
  process.exit(1);
});
