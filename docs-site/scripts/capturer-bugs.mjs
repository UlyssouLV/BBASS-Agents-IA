/**
 * Capture la section Bugs connus de l’accueil → docs/img/apercu-docs-bugs.png (README).
 * Usage : node scripts/capturer-bugs.mjs [url]
 * Défaut : http://127.0.0.1:4173/BBASS-Agents-IA/
 */
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {chromium} from 'playwright';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(__dirname, '../..');
const OUT = path.join(REPO_ROOT, 'docs/img/apercu-docs-bugs.png');
const URL =
  process.argv[2] ||
  process.env.DOCS_CAPTURE_URL ||
  'http://127.0.0.1:4173/BBASS-Agents-IA/';

async function main() {
  fs.mkdirSync(path.dirname(OUT), {recursive: true});
  const browser = await chromium.launch({headless: true});
  const page = await browser.newPage({
    viewport: {width: 960, height: 900},
    deviceScaleFactor: 2,
  });
  await page.goto(URL, {waitUntil: 'networkidle', timeout: 120_000});
  await page.addStyleTag({
    content: `
      .navbar { display: none !important; }
      .main-wrapper { padding-top: 0 !important; }
      [data-readme="bugs-lien-sommaire"] { display: none !important; }
    `,
  });
  const section = page.locator('[data-readme="bugs"]');
  await section.waitFor({state: 'visible', timeout: 30_000});
  await page.locator('[data-readme="bugs"] li').first().waitFor({
    state: 'visible',
    timeout: 30_000,
  });
  await page.waitForTimeout(400);
  await section.screenshot({path: OUT, type: 'png'});
  await browser.close();
  console.log(`[capture] ${OUT} ← ${URL} [data-readme=bugs]`);
}

main().catch((erreur) => {
  console.error('[capture]', erreur);
  process.exit(1);
});
