/**
 * Synchronise l’emploi du temps depuis le dossier externe « Suivi »
 * (Excel de la semaine) → PNG + section #agenda-quotidien du HTML.
 *
 * Source par défaut : <parent-du-repo>/Suivi
 * Surcharge : env BBASS_SUIVI_DIR
 *
 * Dossiers attendus côté Suivi : « Semaine du JJ-MM-AA » (lundi de la semaine).
 * Fichier : premier Semaine*.xlsx, sinon premier *.xlsx.
 *
 * Usage :
 *   node docs/suivi-avancement/sync-agenda.mjs <dossier-semaine|html>
 *   node docs/suivi-avancement/sync-agenda.mjs   # semaine courante (Europe/Paris)
 *
 * Soft-skip si le dossier Suivi / le xlsx est absent (exit 0, message [sync-agenda]).
 * --strict : exit 1 si rien à synchroniser.
 */
import {spawnSync} from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {fileURLToPath, pathToFileURL} from 'node:url';
import {createRequire} from 'node:module';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(__dirname, '../..');
const SUIVI_AVANCEMENT = __dirname;
const OUT_PNG = 'agenda-quotidien-tableau.png';
const XLSX_TO_HTML = path.join(__dirname, 'xlsx-vers-html-agenda.py');

const MOIS = {
  jan: 0,
  fev: 1,
  mar: 2,
  avr: 3,
  mai: 4,
  juin: 5,
  juil: 6,
  aout: 7,
  sept: 8,
  oct: 9,
  nov: 10,
  dec: 11,
};

const MOIS_LABEL = [
  'janvier',
  'février',
  'mars',
  'avril',
  'mai',
  'juin',
  'juillet',
  'août',
  'septembre',
  'octobre',
  'novembre',
  'décembre',
];

function dossierSuiviExterne() {
  if (process.env.BBASS_SUIVI_DIR) {
    return path.resolve(process.env.BBASS_SUIVI_DIR);
  }
  return path.resolve(REPO_ROOT, '..', 'Suivi');
}

function jourParis(date = new Date()) {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Europe/Paris',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(date);
  const y = Number(parts.find((p) => p.type === 'year').value);
  const m = Number(parts.find((p) => p.type === 'month').value) - 1;
  const d = Number(parts.find((p) => p.type === 'day').value);
  return new Date(Date.UTC(y, m, d));
}

function parseSemaineDir(name) {
  const match = /^semaine-(\d{2})-(\d{2})-([a-z]+)-(\d{4})$/.exec(name);
  if (!match) return null;
  const debutJour = Number(match[1]);
  const finJour = Number(match[2]);
  const mois = MOIS[match[3]];
  const annee = Number(match[4]);
  if (mois === undefined || Number.isNaN(debutJour) || Number.isNaN(finJour)) {
    return null;
  }
  const start = new Date(Date.UTC(annee, mois, debutJour));
  const end = new Date(Date.UTC(annee, mois, finJour));
  const label = `semaine du ${String(debutJour).padStart(2, '0')} au ${String(finJour).padStart(2, '0')} ${MOIS_LABEL[mois]} ${annee}`;
  return {name, start, end, label, annee, mois, debutJour, finJour};
}

function listerSemainesRepo() {
  return fs
    .readdirSync(SUIVI_AVANCEMENT, {withFileTypes: true})
    .filter((e) => e.isDirectory())
    .map((e) => parseSemaineDir(e.name))
    .filter(Boolean)
    .sort((a, b) => a.start - b.start);
}

function trouverSemaineCourante() {
  const aujourdHui = jourParis();
  const semaines = listerSemainesRepo();
  if (!semaines.length) {
    throw new Error(`Aucun dossier semaine-* sous ${SUIVI_AVANCEMENT}`);
  }
  const courante = semaines.find(
    (s) => aujourdHui >= s.start && aujourdHui <= s.end,
  );
  if (courante) return courante;
  const passees = semaines.filter((s) => s.end < aujourdHui);
  if (passees.length) return passees[passees.length - 1];
  return semaines[0];
}

function trouverHtmlOuDossier(cible) {
  if (!cible) {
    const s = trouverSemaineCourante();
    return {
      semaineDir: path.join(SUIVI_AVANCEMENT, s.name),
      meta: s,
    };
  }
  const abs = path.resolve(cible);
  if (abs !== SUIVI_AVANCEMENT && !abs.startsWith(SUIVI_AVANCEMENT + path.sep)) {
    throw new Error(`Hors de ${SUIVI_AVANCEMENT} : ${abs}`);
  }
  let semaineDir = abs;
  if (fs.statSync(abs).isFile()) {
    semaineDir = path.dirname(abs);
  }
  const meta = parseSemaineDir(path.basename(semaineDir));
  if (!meta) {
    throw new Error(`Nom de dossier semaine invalide : ${path.basename(semaineDir)}`);
  }
  return {semaineDir, meta};
}

function htmlSuivi(semaineDir) {
  const fichiers = fs
    .readdirSync(semaineDir)
    .filter((f) => /^suivi-semaine-.*\.html$/i.test(f))
    .sort();
  if (!fichiers.length) {
    throw new Error(`Aucun suivi-semaine-*.html dans ${semaineDir}`);
  }
  return path.join(semaineDir, fichiers[0]);
}

/** Candidats « Semaine du JJ-MM-AA » / variantes pour le lundi de la semaine repo. */
function candidatsNomsSuivi(meta) {
  const jj = String(meta.debutJour).padStart(2, '0');
  const j = String(meta.debutJour);
  const mm = String(meta.mois + 1).padStart(2, '0');
  const m = String(meta.mois + 1);
  const aa = String(meta.annee).slice(-2);
  const aaaa = String(meta.annee);
  const bases = [
    `${jj}-${mm}-${aa}`,
    `${j}-${m}-${aa}`,
    `${jj}-${mm}-${aaaa}`,
    `${j}-${m}-${aaaa}`,
  ];
  const noms = [];
  for (const b of bases) {
    noms.push(`Semaine du ${b}`);
    noms.push(`semaine du ${b}`);
  }
  return noms;
}

function trouverDossierSuivi(meta, racineSuivi) {
  if (!fs.existsSync(racineSuivi)) {
    return {ok: false, raison: `Dossier Suivi introuvable : ${racineSuivi}`};
  }
  const entrees = fs.readdirSync(racineSuivi, {withFileTypes: true}).filter((e) => e.isDirectory());
  const nomsExact = new Set(candidatsNomsSuivi(meta));
  const exact = entrees.find((e) => nomsExact.has(e.name));
  if (exact) {
    return {ok: true, dir: path.join(racineSuivi, exact.name)};
  }
  // Souple : dossier dont le nom contient JJ-MM-AA du lundi
  const jj = String(meta.debutJour).padStart(2, '0');
  const mm = String(meta.mois + 1).padStart(2, '0');
  const aa = String(meta.annee).slice(-2);
  const cle = `${jj}-${mm}-${aa}`;
  const flou = entrees.find((e) => e.name.includes(cle));
  if (flou) {
    return {ok: true, dir: path.join(racineSuivi, flou.name)};
  }
  return {
    ok: false,
    raison: `Aucune semaine Suivi pour le lundi ${cle} sous ${racineSuivi} (attendu p.ex. « Semaine du ${cle} »)`,
  };
}

function trouverXlsx(dirSuivi) {
  const fichiers = fs.readdirSync(dirSuivi).filter((f) => /\.xlsx$/i.test(f) && !f.startsWith('~$'));
  if (!fichiers.length) {
    return {ok: false, raison: `Aucun .xlsx dans ${dirSuivi}`};
  }
  const pref = fichiers.find((f) => /^semaine/i.test(f));
  return {ok: true, path: path.join(dirSuivi, pref || fichiers.sort()[0])};
}

/** Premier interpréteur qui importe openpyxl (évite `py` → 3.14 sans deps). */
function pythonExe() {
  const candidats =
    process.platform === 'win32'
      ? [
          ['python', []],
          ['python3', []],
          ['py', ['-3.11']],
          ['py', ['-3']],
        ]
      : [
          ['python3', []],
          ['python', []],
        ];
  for (const [cmd, prefix] of candidats) {
    const probe = spawnSync(
      cmd,
      [...prefix, '-c', 'import openpyxl'],
      {encoding: 'utf8'},
    );
    if (probe.status === 0) return {cmd, prefix};
  }
  throw new Error(
    'Python+openpyxl introuvable (pip install openpyxl sur python 3.11+)',
  );
}

function xlsxVersHtml(xlsxPath, htmlTmp) {
  const {cmd, prefix} = pythonExe();
  const run = spawnSync(
    cmd,
    [...prefix, XLSX_TO_HTML, xlsxPath],
    {encoding: 'utf8', maxBuffer: 16 * 1024 * 1024},
  );
  if (run.status !== 0) {
    const detail = [run.stderr, run.stdout].filter(Boolean).join('\n').trim();
    throw new Error(`xlsx→html échoué\n${detail || '(pas de détail)'}`);
  }
  fs.writeFileSync(htmlTmp, run.stdout, 'utf8');
}

async function capturerPng(htmlTmp, pngPath) {
  const require = createRequire(path.join(REPO_ROOT, 'docs-site', 'package.json'));
  let chromium;
  try {
    ({chromium} = require('playwright'));
  } catch {
    throw new Error(
      'playwright introuvable : lancer `npm install` dans docs-site/',
    );
  }
  const browser = await chromium.launch({headless: true});
  try {
    const page = await browser.newPage({
      viewport: {width: 1280, height: 900},
      deviceScaleFactor: 2,
    });
    await page.goto(pathToFileURL(htmlTmp).href, {
      waitUntil: 'networkidle',
      timeout: 60_000,
    });
    const table = page.locator('#agenda');
    await table.waitFor({state: 'visible', timeout: 15_000});
    await table.screenshot({path: pngPath, type: 'png'});
  } finally {
    await browser.close();
  }
}

function patchHtmlAgenda(htmlPath, alt) {
  let html = fs.readFileSync(htmlPath, 'utf8');
  const img = `<img src="${OUT_PNG}" alt="${alt}" />`;
  const sectionRe =
    /(<section\b[^>]*\bid=["']agenda-quotidien["'][^>]*>)([\s\S]*?)(<\/section>)/i;
  if (!sectionRe.test(html)) {
    const bloc = `
    <section class="bloc agenda" id="agenda-quotidien">
      <h2>Emploi du temps quotidien</h2>
      ${img}
    </section>`;
    if (/<\/div>\s*<\/body>/i.test(html)) {
      html = html.replace(/<\/div>\s*<\/body>/i, `${bloc}\n  </div>\n</body>`);
    } else {
      throw new Error(`Impossible d’insérer #agenda-quotidien dans ${htmlPath}`);
    }
  } else {
    html = html.replace(sectionRe, (_, open, _inner, close) => {
      return `${open}
      <h2>Emploi du temps quotidien</h2>
      ${img}
    ${close}`;
    });
  }
  fs.writeFileSync(htmlPath, html, 'utf8');
}

/**
 * @param {string|undefined} cible dossier semaine ou html
 * @param {{strict?: boolean}} opts
 * @returns {Promise<{synced: boolean, reason?: string, png?: string}>}
 */
export async function syncAgenda(cible, opts = {}) {
  const strict = Boolean(opts.strict);
  const {semaineDir, meta} = trouverHtmlOuDossier(cible);
  const htmlPath = htmlSuivi(semaineDir);
  const racineSuivi = dossierSuiviExterne();
  const dossier = trouverDossierSuivi(meta, racineSuivi);
  if (!dossier.ok) {
    const msg = dossier.raison;
    if (strict) throw new Error(msg);
    console.warn(`[sync-agenda] soft-skip : ${msg}`);
    return {synced: false, reason: msg};
  }
  const xlsx = trouverXlsx(dossier.dir);
  if (!xlsx.ok) {
    if (strict) throw new Error(xlsx.raison);
    console.warn(`[sync-agenda] soft-skip : ${xlsx.raison}`);
    return {synced: false, reason: xlsx.raison};
  }

  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'suivi-agenda-'));
  const htmlTmp = path.join(tmpDir, 'agenda.html');
  const pngPath = path.join(semaineDir, OUT_PNG);
  try {
    xlsxVersHtml(xlsx.path, htmlTmp);
    await capturerPng(htmlTmp, pngPath);
  } finally {
    try {
      fs.rmSync(tmpDir, {recursive: true, force: true});
    } catch {
      /* ignore */
    }
  }

  const alt = `Emploi du temps quotidien — ${meta.label}`;
  patchHtmlAgenda(htmlPath, alt);
  console.log(
    `[sync-agenda] ${path.relative(REPO_ROOT, pngPath)} ← ${xlsx.path}`,
  );
  return {synced: true, png: pngPath};
}

async function mainCli() {
  const args = process.argv.slice(2);
  const strict = args.includes('--strict');
  const cible = args.find((a) => !a.startsWith('-'));
  await syncAgenda(cible, {strict});
}

const isDirect =
  process.argv[1] &&
  path.resolve(process.argv[1]) === fileURLToPath(import.meta.url);

if (isDirect) {
  mainCli().catch((err) => {
    console.error(`[sync-agenda] ${err.message || err}`);
    process.exit(1);
  });
}
