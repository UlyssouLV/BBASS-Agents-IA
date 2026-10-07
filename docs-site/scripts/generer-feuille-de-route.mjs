/**
 * Extrait les prochaines versions de docs/dev/feuille-de-route/feuille-de-route-dev.md
 * → JSON accueil + pages docs/feuille-de-route/vX.Y.Z.md
 */
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(__dirname, '../..');
const SOURCE = path.join(
  REPO_ROOT,
  'docs/dev/feuille-de-route/feuille-de-route-dev.md',
);
const OUT_JSON = path.join(__dirname, '../src/data/feuille-de-route.json');
const OUT_DIR = path.join(REPO_ROOT, 'docs/feuille-de-route');

function extraireObjectif(bloc) {
  const m = bloc.match(
    /\*\*Objectif\.\*\*\s*([\s\S]*?)(?=\n\*\*[A-ZÉÈÀÂÊÎÔÛ]|\n## |\n### |$)/,
  );
  if (!m) {
    const premier = bloc.trim().split(/\n\n/)[0];
    return (premier || '').replace(/\s+/g, ' ').trim();
  }
  return m[1].replace(/\s+/g, ' ').trim();
}

function nettoyerTexte(texte) {
  return texte
    .replace(/\*\*([^*]+)\*\*/g, '$1')
    .replace(/`([^`]+)`/g, '$1')
    .replace(/\s+/g, ' ')
    .trim();
}

function tronquer(texte, max = 180) {
  const propre = nettoyerTexte(texte);
  if (propre.length <= max) {
    return propre;
  }
  const coupe = propre.slice(0, max);
  const dernier = coupe.lastIndexOf(' ');
  return `${coupe.slice(0, dernier > 80 ? dernier : max).trim()}…`;
}

function escapeMdx(text) {
  return String(text)
    .replace(/\{/g, '\\{')
    .replace(/\}/g, '\\}')
    .replace(/<([A-Za-z/])/g, '\\<$1');
}

function escapeYaml(value) {
  return JSON.stringify(String(value ?? ''));
}

function parserEnsuite(markdown) {
  const re = /^## (?:Prochaine|Ensuite) : (\d+\.\d+(?:\.\d+)?)\s*[—–\-]\s*(.+)$/gm;
  const indices = [];
  let match;
  while ((match = re.exec(markdown)) !== null) {
    indices.push({
      version: match[1],
      titre: match[2].trim(),
      start: match.index,
      headerEnd: match.index + match[0].length,
    });
  }
  const versions = [];
  for (let i = 0; i < indices.length; i++) {
    const courant = indices[i];
    const plusTard = markdown.search(/^## Plus tard/m);
    const fin =
      i + 1 < indices.length
        ? indices[i + 1].start
        : plusTard > courant.start
          ? plusTard
          : markdown.length;
    const corps = markdown.slice(courant.headerEnd, fin).trim();
    const slug = `v${courant.version}`;
    versions.push({
      version: courant.version,
      titre: courant.titre,
      resume: tronquer(extraireObjectif(corps)),
      corps,
      slug,
      href: `/docs/feuille-de-route/${slug}`,
    });
  }
  return versions;
}

function parserPlusTard(markdown) {
  const debut = markdown.search(/^## Plus tard/m);
  if (debut < 0) {
    return [];
  }
  const suite = markdown.slice(debut);
  const fin = suite.search(/\n## [^P]/);
  const bloc = fin > 0 ? suite.slice(0, fin) : suite;
  return [...bloc.matchAll(/^### (.+)$/gm)].map((m) => m[1].trim());
}

function resetOutDir() {
  fs.mkdirSync(OUT_DIR, {recursive: true});
  for (const name of fs.readdirSync(OUT_DIR)) {
    if (name === '.gitkeep' || name === 'README.md') {
      continue;
    }
    fs.rmSync(path.join(OUT_DIR, name), {force: true});
  }
}

function ecrirePages(versions) {
  resetOutDir();
  versions.forEach((v, index) => {
    const content = `---
sidebar_label: ${escapeYaml(v.version)}
sidebar_position: ${index + 1}
---

# ${v.version} — ${v.titre}

> Extrait de la feuille de route.

${escapeMdx(v.corps)}
`;
    fs.writeFileSync(path.join(OUT_DIR, `${v.slug}.md`), content, 'utf8');
  });
}

function main() {
  fs.mkdirSync(path.dirname(OUT_JSON), {recursive: true});
  if (!fs.existsSync(SOURCE)) {
    console.warn('[feuille-de-route] fichier introuvable:', SOURCE);
    fs.writeFileSync(
      OUT_JSON,
      `${JSON.stringify({versions: [], plusTard: []}, null, 2)}\n`,
    );
    return;
  }
  const markdown = fs.readFileSync(SOURCE, 'utf8');
  const versions = parserEnsuite(markdown);
  ecrirePages(versions);
  const payload = {
    versions: versions.map(({version, titre, resume, href, slug}) => ({
      version,
      titre,
      resume,
      href,
      slug,
    })),
    plusTard: parserPlusTard(markdown).slice(0, 6),
  };
  fs.writeFileSync(OUT_JSON, `${JSON.stringify(payload, null, 2)}\n`, 'utf8');
  console.log(
    `[feuille-de-route] ${versions.length} version(s) → JSON + docs/feuille-de-route/`,
  );
}

main();
