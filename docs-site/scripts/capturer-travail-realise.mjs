/**
 * Capture la section #travail-realise du suivi HTML de la semaine courante
 * → docs/img/apercu-travail-realise.png (README).
 *
 * Choix du HTML : dossier docs/suivi-avancement/semaine-JJ-JJ-mois-AAAA/
 * dont l’intervalle [JJ début, JJ fin] contient la date du jour (Europe/Paris) ;
 * sinon la semaine la plus récente déjà terminée ; sinon la prochaine.
 *
 * Usage : node scripts/capturer-travail-realise.mjs
 */
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath, pathToFileURL} from 'node:url';
import {chromium} from 'playwright';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(__dirname, '../..');
const SUIVI_ROOT = path.join(REPO_ROOT, 'docs/suivi-avancement');
const OUT = path.join(REPO_ROOT, 'docs/img/apercu-travail-realise.png');
const README = path.join(REPO_ROOT, 'README.md');

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
  const label = `Semaine du ${String(debutJour).padStart(2, '0')} au ${String(finJour).padStart(2, '0')} ${MOIS_LABEL[mois]} ${annee}`;
  return {name, start, end, label};
}

function listerSemaines() {
  if (!fs.existsSync(SUIVI_ROOT)) return [];
  return fs
    .readdirSync(SUIVI_ROOT, {withFileTypes: true})
    .filter((e) => e.isDirectory())
    .map((e) => parseSemaineDir(e.name))
    .filter(Boolean)
    .sort((a, b) => a.start - b.start);
}

function trouverSemaine(aujourdHui, semaines) {
  if (semaines.length === 0) {
    throw new Error(`Aucun dossier semaine-* sous ${SUIVI_ROOT}`);
  }
  const courante = semaines.find(
    (s) => aujourdHui >= s.start && aujourdHui <= s.end,
  );
  if (courante) return courante;
  const passees = semaines.filter((s) => s.end < aujourdHui);
  if (passees.length) return passees[passees.length - 1];
  return semaines[0];
}

function trouverHtml(dirName) {
  const dir = path.join(SUIVI_ROOT, dirName);
  const fichiers = fs
    .readdirSync(dir)
    .filter((f) => /^suivi-semaine-.*\.html$/i.test(f))
    .sort();
  if (!fichiers.length) {
    throw new Error(`Aucun suivi-semaine-*.html dans ${dir}`);
  }
  return path.join(dir, fichiers[0]);
}

function majTitreReadme(label) {
  if (!fs.existsSync(README)) return;
  const avant = fs.readFileSync(README, 'utf8');
  const apres = avant.replace(
    /^## Semaine du .+$/m,
    `## ${label}`,
  );
  if (apres !== avant) {
    fs.writeFileSync(README, apres, 'utf8');
    console.log(`[capture] README → ## ${label}`);
  }
}

async function main() {
  const aujourdHui = jourParis();
  const semaine = trouverSemaine(aujourdHui, listerSemaines());
  const htmlPath = trouverHtml(semaine.name);
  const url = pathToFileURL(htmlPath).href;

  fs.mkdirSync(path.dirname(OUT), {recursive: true});
  const browser = await chromium.launch({headless: true});
  const page = await browser.newPage({
    viewport: {width: 900, height: 1200},
    deviceScaleFactor: 2,
  });
  await page.goto(url, {waitUntil: 'networkidle', timeout: 60_000});
  const section = page.locator('#travail-realise');
  await section.waitFor({state: 'visible', timeout: 15_000});
  // README : pas de titre ni de puces (le contenu des jours reste)
  await page.addStyleTag({
    content: `
      #travail-realise > h2 { display: none !important; }
      #travail-realise ul { list-style: none !important; padding-left: 0 !important; }
    `,
  });
  await page.waitForTimeout(200);
  await section.screenshot({path: OUT, type: 'png'});
  await browser.close();

  majTitreReadme(semaine.label);
  console.log(`[capture] ${OUT}`);
  console.log(`[capture] ${semaine.label} ← ${path.relative(REPO_ROOT, htmlPath)}`);
}

main().catch((erreur) => {
  console.error('[capture]', erreur);
  process.exit(1);
});
