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
    viewport: {width: 720, height: 900},
    deviceScaleFactor: 2,
  });
  await page.goto(URL, {waitUntil: 'networkidle', timeout: 120_000});
  await page.addStyleTag({
    content: `
      .navbar { display: none !important; }
      .main-wrapper { padding-top: 0 !important; }
      [data-readme="bugs"] > h2 { display: none !important; }
      [data-readme="bugs-lien-sommaire"] { display: none !important; }
      [data-readme="bugs"] ol {
        margin-top: 0 !important;
        max-width: 100% !important;
      }
      [data-readme="bugs"] a {
        grid-template-columns: 0.9rem 1fr !important;
        gap: 0.45rem 0.65rem !important;
        padding: 0.45rem 0 !important;
      }
      [data-readme="bugs"] a > span:last-child { display: none !important; }
      [data-readme="bugs"] [class*="issue"],
      [data-readme="bugs"] [class*="priorite"] {
        font-size: 0.68rem !important;
      }
      [data-readme="bugs"] [class*="titre"] {
        font-size: 0.82rem !important;
        line-height: 1.3 !important;
      }
      [data-readme="bugs"] [class*="resume"] {
        font-size: 0.72rem !important;
        line-height: 1.35 !important;
      }
      [data-readme="bugs"] [class*="manques"] {
        font-size: 0.65rem !important;
      }
      [data-readme="bugs"] [class*="point"] {
        width: 0.4rem !important;
        height: 0.4rem !important;
      }
      [data-readme="bugs"] [class*="corps"] {
        gap: 0.12rem !important;
      }
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
