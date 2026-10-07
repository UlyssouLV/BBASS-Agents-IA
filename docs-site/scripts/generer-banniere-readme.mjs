/**
 * Bannière README : logo BBASS + texte « Agents IA » (style Graphite).
 * Usage : node scripts/generer-banniere-readme.mjs
 */
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {pathToFileURL} from 'node:url';
import {chromium} from 'playwright';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(__dirname, '../..');
const LOGO = path.join(REPO_ROOT, 'docs-site/static/img/logo-bbass.png');
const OUT = path.join(REPO_ROOT, 'docs/img/readme-banniere.png');
const HTML = path.join(__dirname, '.banniere-readme.html');

const html = `<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8" />
<style>
  @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@500;700;800&display=swap');
  * { box-sizing: border-box; margin: 0; padding: 0; }
  html, body {
    background: #fff;
    width: 1100px;
    height: 280px;
  }
  .wrap {
    width: 1100px;
    height: 280px;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 2.75rem;
    padding: 1.5rem 2rem;
    background: #fff;
    font-family: Outfit, system-ui, sans-serif;
  }
  .logo {
    height: 168px;
    width: auto;
    display: block;
  }
  .sep {
    width: 3px;
    height: 120px;
    border-radius: 2px;
    background: linear-gradient(180deg, transparent, #c8102e 18%, #c8102e 82%, transparent);
    flex-shrink: 0;
  }
  .agents {
    display: flex;
    flex-direction: column;
    justify-content: center;
    line-height: 0.92;
    letter-spacing: -0.03em;
  }
  .agents .ligne1 {
    font-size: 72px;
    font-weight: 800;
    color: #1a1a1a;
  }
  .agents .ligne2 {
    font-size: 72px;
    font-weight: 800;
    color: #c8102e;
    font-style: italic;
    letter-spacing: -0.02em;
  }
</style>
</head>
<body>
  <div class="wrap">
    <img class="logo" src="${pathToFileURL(LOGO).href}" alt="BBASS" />
    <div class="sep" aria-hidden="true"></div>
    <div class="agents">
      <span class="ligne1">Agents</span>
      <span class="ligne2">IA</span>
    </div>
  </div>
</body>
</html>
`;

async function main() {
  fs.mkdirSync(path.dirname(OUT), {recursive: true});
  fs.writeFileSync(HTML, html, 'utf8');
  const browser = await chromium.launch({headless: true});
  const page = await browser.newPage({
    viewport: {width: 1100, height: 280},
    deviceScaleFactor: 2,
  });
  await page.goto(pathToFileURL(HTML).href, {waitUntil: 'networkidle', timeout: 60_000});
  await page.waitForTimeout(600);
  await page.screenshot({
    path: OUT,
    type: 'png',
    omitBackground: false,
  });
  await browser.close();
  fs.unlinkSync(HTML);
  console.log(`[bannière] ${OUT}`);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
