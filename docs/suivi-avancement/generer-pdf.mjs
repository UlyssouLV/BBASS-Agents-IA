/**
 * Régénère le PDF sibling d’un suivi HTML (Chrome / Edge headless).
 *
 * Usage :
 *   node docs/suivi-avancement/generer-pdf.mjs <chemin.html>
 *   node docs/suivi-avancement/generer-pdf.mjs <dossier-semaine/>
 *
 * Si un dossier est passé : prend le premier suivi-semaine-*.html dedans.
 * La cible doit être sous docs/suivi-avancement/ : tout autre chemin est refusé.
 * Sortie : même nom que le HTML, extension .pdf, à côté.
 *
 * Prérequis : Google Chrome ou Microsoft Edge installé (chemins Windows / macOS / Linux usuels).
 */
import {spawnSync} from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {fileURLToPath, pathToFileURL} from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

function trouverHtml(cible) {
  const abs = path.resolve(cible);
  if (abs !== __dirname && !abs.startsWith(__dirname + path.sep)) {
    throw new Error(`Hors de ${__dirname} : ${abs}`);
  }
  if (!fs.existsSync(abs)) {
    throw new Error(`Introuvable : ${abs}`);
  }
  const st = fs.statSync(abs);
  if (st.isFile()) {
    if (!/\.html?$/i.test(abs)) {
      throw new Error(`Pas un HTML : ${abs}`);
    }
    return abs;
  }
  const fichiers = fs
    .readdirSync(abs)
    .filter((f) => /^suivi-semaine-.*\.html$/i.test(f))
    .sort();
  if (!fichiers.length) {
    throw new Error(`Aucun suivi-semaine-*.html dans ${abs}`);
  }
  return path.join(abs, fichiers[0]);
}

function candidatsChrome() {
  const home = os.homedir();
  const plat = process.platform;
  if (plat === 'win32') {
    const local = process.env.LOCALAPPDATA || '';
    const pf = process.env['PROGRAMFILES'] || 'C:\\Program Files';
    const pf86 = process.env['PROGRAMFILES(X86)'] || 'C:\\Program Files (x86)';
    return [
      path.join(local, 'Google', 'Chrome', 'Application', 'chrome.exe'),
      path.join(pf, 'Google', 'Chrome', 'Application', 'chrome.exe'),
      path.join(pf86, 'Google', 'Chrome', 'Application', 'chrome.exe'),
      path.join(local, 'Microsoft', 'Edge', 'Application', 'msedge.exe'),
      path.join(pf, 'Microsoft', 'Edge', 'Application', 'msedge.exe'),
      path.join(pf86, 'Microsoft', 'Edge', 'Application', 'msedge.exe'),
    ];
  }
  if (plat === 'darwin') {
    return [
      '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
      '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge',
      path.join(home, 'Applications', 'Google Chrome.app', 'Contents', 'MacOS', 'Google Chrome'),
    ];
  }
  return [
    '/usr/bin/google-chrome',
    '/usr/bin/google-chrome-stable',
    '/usr/bin/chromium',
    '/usr/bin/chromium-browser',
    '/usr/bin/microsoft-edge',
    '/usr/bin/microsoft-edge-stable',
  ];
}

function trouverNavigateur() {
  for (const c of candidatsChrome()) {
    if (c && fs.existsSync(c)) return c;
  }
  throw new Error(
    'Aucun Chrome/Edge trouvé. Installe Google Chrome ou Microsoft Edge, ou lance la commande manuellement (voir README).',
  );
}

function estVerrouille(pdfPath) {
  if (!fs.existsSync(pdfPath)) return false;
  try {
    const fd = fs.openSync(pdfPath, 'r+');
    fs.closeSync(fd);
    return false;
  } catch (err) {
    if (err && (err.code === 'EBUSY' || err.code === 'EPERM' || err.code === 'EACCES')) {
      return true;
    }
    return false;
  }
}

function main() {
  const arg = process.argv[2];
  if (!arg) {
    console.error(
      'Usage : node docs/suivi-avancement/generer-pdf.mjs <html|dossier-semaine>',
    );
    process.exit(2);
  }
  const htmlPath = trouverHtml(arg);
  const pdfPath = htmlPath.replace(/\.html?$/i, '.pdf');
  if (estVerrouille(pdfPath)) {
    throw new Error(
      `PDF verrouillé (ouvert ailleurs ?) : ${pdfPath}\nFerme le fichier puis relance.`,
    );
  }

  const browser = trouverNavigateur();
  const fileUrl = pathToFileURL(htmlPath).href;
  const args = [
    '--headless=new',
    '--disable-gpu',
    '--no-pdf-header-footer',
    `--print-to-pdf=${pdfPath}`,
    fileUrl,
  ];

  const run = spawnSync(browser, args, {encoding: 'utf8'});
  if (run.status !== 0) {
    const detail = [run.stderr, run.stdout].filter(Boolean).join('\n').trim();
    throw new Error(
      `Échec print-to-pdf (code ${run.status}) via ${browser}\n${detail || '(pas de détail)'}`,
    );
  }
  if (!fs.existsSync(pdfPath) || fs.statSync(pdfPath).size < 100) {
    throw new Error(`PDF absent ou vide après génération : ${pdfPath}`);
  }
  console.log(`[suivi-pdf] ${path.relative(path.join(__dirname, '../..'), pdfPath)}`);
}

try {
  main();
} catch (err) {
  console.error(`[suivi-pdf] ${err.message || err}`);
  process.exit(1);
}
