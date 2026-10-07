/**
 * Capture l’accueil du site de doc (PNG pour le README).
 * Usage :
 *   node scripts/capturer-accueil.mjs [url]
 * Défaut : http://127.0.0.1:4173/BBASS-Agents-IA/
 */
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {chromium} from 'playwright';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(__dirname, '../..');
const OUT = path.join(REPO_ROOT, 'docs/img/apercu-docs-accueil.png');
const URL =
  process.argv[2] ||
  process.env.DOCS_CAPTURE_URL ||
  'http://127.0.0.1:4173/BBASS-Agents-IA/';

async function main() {
  fs.mkdirSync(path.dirname(OUT), {recursive: true});
  const browser = await chromium.launch({headless: true});
  const page = await browser.newPage({
    viewport: {width: 1440, height: 900},
    deviceScaleFactor: 2,
  });
  await page.goto(URL, {waitUntil: 'networkidle', timeout: 120_000});
  // Masque chrome / intro / bugs (section Bugs = capture séparée)
  await page.addStyleTag({
    content: `
      .navbar { display: none !important; }
      .main-wrapper { padding-top: 0 !important; }
      main h1 + p { display: none !important; }
      main p:has(a.button) { display: none !important; }
      main p:has(a[href*="/docs/changelog"]) { display: none !important; }
      [data-readme="bugs"] { display: none !important; }
    `,
  });
  await page.waitForTimeout(400);
  await page.screenshot({
    path: OUT,
    type: 'png',
    fullPage: false,
  });
  await browser.close();
  console.log(`[capture] ${OUT} ← ${URL}`);
}

main().catch((erreur) => {
  console.error('[capture]', erreur);
  process.exit(1);
});
