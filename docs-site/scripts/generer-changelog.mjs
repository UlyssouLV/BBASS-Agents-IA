/**
 * Génère docs/changelog/ à partir des GitHub Releases + specs locales.
 * Versions groupées par série (1.4, 1.3, …) pour la sidebar.
 */
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

import {escapeMdx, escapeYaml} from './echappement.mjs';

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
  // Pas de flag `m` : avec `m`, `$` matche en fin de chaque ligne et coupe au 1er §
  const esc = heading.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const re = new RegExp(
    `(?:^|\\n)##\\s+${esc}\\s*\\n([\\s\\S]*?)(?=\\n##\\s+|$)`,
    'i',
  );
  const m = markdown.match(re);
  return m ? m[1].trim() : '';
}

/** Prépare le body release pour extraction : annotations + titres collés. */
function normalizeReleaseBody(body) {
  let text = String(body || '').replace(/^\uFEFF/, '');
  // Titres ## / ### collés après du texte (annotations mashées)
  text = text.replace(/([^\n])\s+(#{2,3}\s+)/g, '$1\n\n$2');
  // "## Pourquoi  Le modèle…" (titre + corps sur la même ligne)
  text = text.replace(/^(#{2,3}\s+[^\n]+?)\s{2,}(?=\S)/gm, '$1\n\n');
  // Nouveau bloc d'annotation collé
  text = text.replace(/([^\n])\s+(> \*\*Modifié en)/g, '$1\n\n$2');
  // Retire les blockquotes d'annotation en tête (Modifié en VX.Y.Z)
  text = text.replace(
    /^(?:>\s*\*\*Modifié en[\s\S]*?\n)(?=\n|#{2,3}\s|$)/gim,
    '',
  );
  // Encore des lignes > orphelines en tête
  while (/^>\s?/m.test(text) && !/^#{2,3}\s/m.test(text.slice(0, 80))) {
    const next = text.replace(/^(?:>.*(?:\n|$))+/, '').trimStart();
    if (next === text) break;
    text = next;
  }
  return text.trim();
}

function extractFunctional(body) {
  const normalized = normalizeReleaseBody(body);
  const pourquoi =
    extractSection(normalized, 'Pourquoi') ||
    extractSection(normalized, 'Objectif') ||
    extractSection(normalized, 'À quoi sert cette version');
  const ceQuonPeut =
    extractSection(normalized, "Ce qu'on peut faire maintenant") ||
    extractSection(normalized, 'Ce qu’on peut faire maintenant') ||
    extractSection(normalized, 'Ce que l’on peut faire') ||
    extractSection(normalized, "Ce que ça change pour l'utilisateur") ||
    extractSection(normalized, 'Ce que ça change') ||
    extractSection(normalized, 'Ce qui est livré');
  // ### sous-titres (ex. anciennes notes 1.2.1) — pas de flag `m` (sinon `$` coupe au 1er §)
  const faireH3 = normalized.match(
    /(?:^|\n)###\s+Ce qu['’]on peut faire maintenant\s*\n([\s\S]*?)(?=\n#{2,3}\s+|$)/i,
  );
  const parts = [];
  if (pourquoi) {
    parts.push(`## Pourquoi\n\n${pourquoi}`);
  }
  const faire = ceQuonPeut || (faireH3 ? faireH3[1].trim() : '');
  if (faire) {
    parts.push(`## Ce qu'on peut faire maintenant\n\n${faire}`);
  }
  if (parts.length === 0) {
    // Notes d'avant le format (autres titres) : le corps tel quel, sans les
    // lignes PR / Tickets déjà portées par <LiensRelease>.
    const brut = normalized
      .replace(/^.*(?:PR\s*:\s*https:|Tickets\s*\(`Fixes`\)).*$/gim, '')
      .replace(/\n{3,}/g, '\n\n')
      .trim();
    return (
      brut ||
      '_Aucune note produit structurée (Pourquoi / Ce qu’on peut faire) dans la release._'
    );
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
  // Le parent (issue de la version) vient en premier (format des notes,
  // agents/issue-tracker.md) ; un numéro répété n'est gardé qu'une fois.
  return [...new Set([...m[1].matchAll(/#(\d+)/g)].map((x) => x[1]))];
}

function stripSpecTitle(specMarkdown) {
  return specMarkdown.replace(/^#\s+[^\n]+\n+/, '').trim();
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

  const specUrl = specRel
    ? `https://github.com/${OWNER}/${REPO}/blob/${tag}/${specRel}`
    : null;
  const specLabel = specRel ? path.basename(specRel) : null;
  const ticketsJsx = fixes
    .map(
      (n) =>
        `{number: ${JSON.stringify(n)}, href: ${JSON.stringify(`https://github.com/${OWNER}/${REPO}/issues/${n}`)}}`,
    )
    .join(', ');
  const prNum = prUrl?.match(/\/pull\/(\d+)/)?.[1];

  const slug = `v${version}`;
  const serieDir = path.join(OUT_DIR, serie);
  fs.mkdirSync(serieDir, {recursive: true});

  const content = `---
sidebar_label: ${escapeYaml(tag)}
sidebar_position: ${positionInSerie}
---

import LiensRelease from '@site/src/components/LiensRelease';
import SectionDoc from '@site/src/components/SectionDoc';

# ${release.name || tag}

Publiée le **${published}**.

<LiensRelease
  releaseUrl=${JSON.stringify(releaseUrl)}
  releaseLabel=${JSON.stringify(tag)}
  prUrl={${prUrl ? JSON.stringify(prUrl) : 'null'}}
  prLabel={${prNum ? JSON.stringify(`#${prNum}`) : 'null'}}
  specUrl={${specUrl ? JSON.stringify(specUrl) : 'null'}}
  specLabel={${specLabel ? JSON.stringify(specLabel) : 'null'}}
  tickets={[${ticketsJsx}]}
/>

<SectionDoc variante="fonctionnelle">

${escapeMdx(functional)}

</SectionDoc>

<SectionDoc
  variante="technique"
  sousTitre={${JSON.stringify(
    specRel
      ? `Spec versionnée : ${specRel}`
      : 'Pas de spec locale pour cette version',
  )}}
>

${escapeMdx(technical)}

</SectionDoc>
`;

  fs.writeFileSync(path.join(serieDir, `${slug}.mdx`), content, 'utf8');
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
    fs.rmSync(path.join(OUT_DIR, name), {
      recursive: true,
      force: true,
      maxRetries: 5,
      retryDelay: 100,
    });
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
