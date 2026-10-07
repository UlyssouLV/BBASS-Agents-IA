/**
 * Génère docs/changelog/ à partir des GitHub Releases + specs locales.
 * Versions groupées par série (1.4, 1.3, …) pour la sidebar.
 */
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(__dirname, '../..');
const OUT_DIR = path.join(REPO_ROOT, 'docs/changelog');
const SPECS_DIR = path.join(REPO_ROOT, 'docs/specs');
const OWNER = process.env.GITHUB_REPOSITORY_OWNER || 'UlyssouLV';
const REPO = (process.env.GITHUB_REPOSITORY || 'UlyssouLV/BBASS-Agents-IA').split(
  '/',
)[1];

function authHeaders() {
  const headers = {
    Accept: 'application/vnd.github+json',
    'X-GitHub-Api-Version': '2022-11-28',
    'User-Agent': 'bbass-docs-changelog',
  };
  const token = process.env.GITHUB_TOKEN || process.env.GH_TOKEN;
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }
  return headers;
}

async function fetchReleases() {
  const releases = [];
  let page = 1;
  for (;;) {
    const url = `https://api.github.com/repos/${OWNER}/${REPO}/releases?per_page=100&page=${page}`;
    const res = await fetch(url, {headers: authHeaders()});
    if (!res.ok) {
      throw new Error(`GitHub releases ${res.status}: ${await res.text()}`);
    }
    const batch = await res.json();
    if (!Array.isArray(batch) || batch.length === 0) {
      break;
    }
    releases.push(...batch);
    if (batch.length < 100) {
      break;
    }
    page += 1;
  }
  return releases.filter((r) => !r.draft);
}

function versionFromTag(tag) {
  return String(tag || '').replace(/^v/i, '');
}

/** « 1.4.2 » → « 1.4 » ; « 1.0.0 » → « 1.0 » ; « 1.1 » → « 1.1 » */
function serieFromVersion(version) {
  const parts = String(version).split('.');
  if (parts.length >= 2) {
    return `${parts[0]}.${parts[1]}`;
  }
  return version;
}

function formatDateFr(iso) {
  const jour = String(iso || '').slice(0, 10);
  if (!/^\d{4}-\d{2}-\d{2}$/.test(jour)) {
    return '—';
  }
  const [annee, mois, jourNum] = jour.split('-');
  return `${jourNum}/${mois}/${annee}`;
}

function titreSansVersion(name, tag) {
  const version = versionFromTag(tag);
  const brut = String(name || tag || '').trim();
  const sans = brut
    .replace(new RegExp(`^v?${version.replace(/\./g, '\\.')}\\s*[—–\\-]\\s*`, 'i'), '')
    .trim();
  return sans || brut;
}

function findSpecFile(version) {
  if (!fs.existsSync(SPECS_DIR)) {
    return null;
  }
  const prefix = `v${version}-`;
  const exact = `v${version}.md`;
  const files = fs.readdirSync(SPECS_DIR).filter((f) => f.endsWith('.md'));
  const match =
    files.find((f) => f === exact) ||
    files.find((f) => f.startsWith(prefix)) ||
    files.find((f) => f.toLowerCase().startsWith(`v${version.toLowerCase()}`));
  return match ? path.join(SPECS_DIR, match) : null;
}

function extractSection(markdown, heading) {
  const re = new RegExp(
    `^##\\s+${heading}\\s*\\n([\\s\\S]*?)(?=^##\\s+|$)`,
    'mi',
  );
  const m = markdown.match(re);
  return m ? m[1].trim() : '';
}

function extractFunctional(body) {
  const pourquoi = extractSection(body, 'Pourquoi');
  const faire = extractSection(body, "Ce qu'on peut faire maintenant");
  const faireAlt = extractSection(body, 'Ce qu’on peut faire maintenant');
  const ceQuonPeut = faire || faireAlt;
  const parts = [];
  if (pourquoi) {
    parts.push(`## Pourquoi\n\n${pourquoi}`);
  }
  if (ceQuonPeut) {
    parts.push(`## Ce qu'on peut faire maintenant\n\n${ceQuonPeut}`);
  }
  if (parts.length === 0) {
    const stripped = body
      .replace(/^>(?:.|\n)*?(?=\n## |\n*$)/m, '')
      .trim();
    return stripped || '_Aucune note de release._';
  }
  return parts.join('\n\n');
}

function extractPrUrl(body) {
  const m = body.match(
    /PR\s*:\s*(https:\/\/github\.com\/[^\s]+\/pull\/\d+)/i,
  );
  return m ? m[1] : null;
}

function extractFixes(body) {
  const m = body.match(/Tickets\s*\(`Fixes`\)\s*:\s*([^\n]+)/i);
  if (!m) {
    return [];
  }
  return [...m[1].matchAll(/#(\d+)/g)].map((x) => x[1]);
}

function stripSpecTitle(specMarkdown) {
  return specMarkdown.replace(/^#\s+[^\n]+\n+/, '').trim();
}

function escapeYaml(value) {
  return JSON.stringify(String(value ?? ''));
}

function escapeMdx(text) {
  return String(text)
    .replace(/\{/g, '\\{')
    .replace(/\}/g, '\\}')
    .replace(/<([A-Za-z/])/g, '\\<$1');
}

function writeVersionPage(release, specPath, positionInSerie) {
  const tag = release.tag_name;
  const version = versionFromTag(tag);
  const serie = serieFromVersion(version);
  const body = release.body || '';
  const functional = extractFunctional(body);
  const prUrl = extractPrUrl(body);
  const fixes = extractFixes(body);
  const publishedIso = (release.published_at || release.created_at || '').slice(
    0,
    10,
  );
  const published = formatDateFr(publishedIso);
  const titre = titreSansVersion(release.name || tag, tag);
  const releaseUrl = release.html_url;

  let technical = '_Pas de spec locale trouvée pour cette version._';
  let specRel = null;
  if (specPath && fs.existsSync(specPath)) {
    specRel = path.relative(REPO_ROOT, specPath).replace(/\\/g, '/');
    technical = stripSpecTitle(fs.readFileSync(specPath, 'utf8'));
  }

  const liens = [
    `- [Release GitHub](${releaseUrl})`,
    prUrl ? `- [Pull request](${prUrl})` : null,
    specRel
      ? `- Spec : [\`${specRel}\`](https://github.com/${OWNER}/${REPO}/blob/${tag}/${specRel})`
      : null,
    fixes.length
      ? `- Tickets : ${fixes.map((n) => `[#${n}](https://github.com/${OWNER}/${REPO}/issues/${n})`).join(' ')}`
      : null,
  ]
    .filter(Boolean)
    .join('\n');

  const slug = `v${version}`;
  const serieDir = path.join(OUT_DIR, serie);
  fs.mkdirSync(serieDir, {recursive: true});

  const content = `---
sidebar_label: ${escapeYaml(tag)}
sidebar_position: ${positionInSerie}
---

# ${release.name || tag}

Publiée le **${published}**.

## Liens

${liens}

## Documentation fonctionnelle

> Extrait de la [release ${tag}](${releaseUrl}) (sections produit).

${escapeMdx(functional)}

## Documentation technique

> Spec versionnée dans le dépôt${specRel ? ` (\`${specRel}\`)` : ''}.

${escapeMdx(technical)}
`;

  fs.writeFileSync(path.join(serieDir, `${slug}.md`), content, 'utf8');
  return {
    tag,
    name: release.name || tag,
    titre,
    published,
    publishedIso,
    slug,
    serie,
    href: `/docs/changelog/${serie}/${slug}`,
  };
}

function writeSerieCategories(seriesOrder) {
  seriesOrder.forEach((serie, index) => {
    fs.writeFileSync(
      path.join(OUT_DIR, serie, '_category_.json'),
      JSON.stringify(
        {
          label: serie,
          position: index + 1,
          collapsed: index !== 0,
        },
        null,
        2,
      ),
      'utf8',
    );
  });
}

function writeIndex() {
  const content = `---
sidebar_position: 0
sidebar_label: Sommaire
---

import ChangelogListe from '@site/src/components/ChangelogListe';

# Changelog

Versions du produit, de la plus récente à la plus ancienne.

<ChangelogListe groupes />
`;

  fs.writeFileSync(path.join(OUT_DIR, 'index.mdx'), content, 'utf8');
}

function writeAccueilJson(entries) {
  const dataDir = path.join(__dirname, '../src/data');
  fs.mkdirSync(dataDir, {recursive: true});
  const payload = entries.map((e) => ({
    version: e.tag,
    serie: e.serie,
    date: e.published,
    dateIso: e.publishedIso || '',
    titre: e.titre,
    href: e.href,
  }));
  fs.writeFileSync(
    path.join(dataDir, 'changelog.json'),
    `${JSON.stringify(payload, null, 2)}\n`,
    'utf8',
  );
}

function resetOutDir() {
  fs.mkdirSync(OUT_DIR, {recursive: true});
  for (const name of fs.readdirSync(OUT_DIR)) {
    if (name === '.gitkeep' || name === 'README.md') {
      continue;
    }
    fs.rmSync(path.join(OUT_DIR, name), {recursive: true, force: true});
  }
  fs.writeFileSync(
    path.join(OUT_DIR, '_category_.json'),
    JSON.stringify(
      {
        label: 'Changelog',
        position: 1,
        collapsed: false,
      },
      null,
      2,
    ),
    'utf8',
  );
}

async function main() {
  resetOutDir();
  let releases;
  try {
    releases = await fetchReleases();
  } catch {
    console.error('[changelog] Impossible de lire les releases GitHub.');
    writeIndex();
    writeAccueilJson([]);
    process.exitCode = 0;
    return;
  }

  // Grouper par série en gardant l’ordre DESC global
  const parSerie = new Map();
  for (const release of releases) {
    const version = versionFromTag(release.tag_name);
    const serie = serieFromVersion(version);
    if (!parSerie.has(serie)) {
      parSerie.set(serie, []);
    }
    parSerie.get(serie).push(release);
  }

  const seriesOrder = [...parSerie.keys()];
  const entries = [];
  for (const serie of seriesOrder) {
    const lot = parSerie.get(serie);
    lot.forEach((release, indexDansSerie) => {
      const version = versionFromTag(release.tag_name);
      const specPath = findSpecFile(version);
      entries.push(writeVersionPage(release, specPath, indexDansSerie + 1));
    });
  }

  writeSerieCategories(seriesOrder);
  writeIndex();
  writeAccueilJson(entries);
  console.log(
    `[changelog] ${entries.length} version(s) en ${seriesOrder.length} série(s) → docs/changelog/`,
  );
}

await main();
