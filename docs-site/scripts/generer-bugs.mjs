/**
 * Extrait les ### Bug — … de docs/dev/feuille-de-route/feuille-de-route-dev.md
 * → JSON accueil + pages docs/bugs/bug-<n>.md
 */
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

import {escapeMdx, escapeYaml} from './echappement.mjs';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(__dirname, '../..');
const SOURCE = path.join(
  REPO_ROOT,
  'docs/dev/feuille-de-route/feuille-de-route-dev.md',
);
const OUT_JSON = path.join(__dirname, '../src/data/bugs.json');
const OUT_DIR = path.join(REPO_ROOT, 'docs/bugs');

const JETON = 'Informations manquantes';

const RUBRIQUES = [
  'Constat',
  'Reproductibilité',
  'Impact',
  'Cause probable',
  'À corriger',
  'Hors périmètre',
  'Suivi',
];

function nettoyerTexte(texte) {
  return texte
    .replace(/\*\*([^*]+)\*\*/g, '$1')
    .replace(/`([^`]+)`/g, '$1')
    .replace(/\s+/g, ' ')
    .trim();
}

function tronquer(texte, max = 140) {
  const propre = nettoyerTexte(texte);
  if (propre.length <= max) {
    return propre;
  }
  const coupe = propre.slice(0, max);
  const dernier = coupe.lastIndexOf(' ');
  return `${coupe.slice(0, dernier > 60 ? dernier : max).trim()}…`;
}

function extraireChamp(corps, nom) {
  const re = new RegExp(
    `\\*\\*${nom}\\s*:\\*\\*\\s*([\\s\\S]*?)(?=\\n\\*\\*[^*]+\\s*:\\*\\*|\\n### |$)`,
    'i',
  );
  const m = corps.match(re);
  if (!m) {
    return JETON;
  }
  return m[1].replace(/\s+/g, ' ').trim() || JETON;
}

function extraireMetaSuivi(suivi) {
  const issueMatch = suivi.match(/#(\d+)/);
  const urlMatch = suivi.match(/\((https:\/\/github\.com\/[^)]+)\)/);
  const trouve = suivi.match(/Trouvé dans\s*:\s*([^·\n]+)/i);
  const contexte = suivi.match(/Contexte\s*:\s*([^·\n]+)/i);
  const date = suivi.match(/Date\s*:\s*([^·\n]+)/i);
  const priorite = suivi.match(/Priorité\s*:\s*([^·\n.]+)/i);
  return {
    issue: issueMatch ? Number(issueMatch[1]) : null,
    url: urlMatch ? urlMatch[1].trim() : null,
    trouveDans: trouve ? trouve[1].trim() : JETON,
    contexte: contexte ? contexte[1].trim() : JETON,
    date: date ? date[1].trim() : JETON,
    priorite: priorite ? priorite[1].trim() : JETON,
  };
}

function champsManquants(champs) {
  const manques = [];
  for (const [cle, valeur] of Object.entries(champs)) {
    if (String(valeur).includes(JETON)) {
      manques.push(cle);
    }
  }
  return manques;
}

function parserBugs(markdown) {
  const debut = markdown.search(/^## Plus tard/m);
  if (debut < 0) {
    return [];
  }
  const suite = markdown.slice(debut);
  // Fin de section : le prochain titre ##, quel qu'il soit.
  const finSection = suite.search(/\n## /);
  const bloc = finSection > 0 ? suite.slice(0, finSection) : suite;

  const reTitre = /^### Bug — (.+?)(?:\s*\(#(\d+)\))?\s*$/gm;
  const indices = [];
  let match;
  while ((match = reTitre.exec(bloc)) !== null) {
    indices.push({
      titre: match[1].trim(),
      issueHeader: match[2] ? Number(match[2]) : null,
      start: match.index,
      headerEnd: match.index + match[0].length,
    });
  }

  const bugs = [];
  for (let i = 0; i < indices.length; i++) {
    const courant = indices[i];
    const fin =
      i + 1 < indices.length ? indices[i + 1].start : bloc.length;
    const corps = bloc.slice(courant.headerEnd, fin).trim();

    const champs = {};
    for (const nom of RUBRIQUES) {
      champs[nom] = extraireChamp(corps, nom);
    }
    const meta = extraireMetaSuivi(champs.Suivi);
    const issue = courant.issueHeader ?? meta.issue;
    if (!issue) {
      console.warn(
        `[bugs] entrée sans #n ignorée: Bug — ${courant.titre}`,
      );
      continue;
    }

    const detail = {
      constat: champs.Constat,
      reproductibilite: champs['Reproductibilité'],
      impact: champs.Impact,
      causeProbable: champs['Cause probable'],
      aCorriger: champs['À corriger'],
      horsPerimetre: champs['Hors périmètre'],
      trouveDans: meta.trouveDans,
      contexte: meta.contexte,
      date: meta.date,
      priorite: meta.priorite,
    };
    const manques = champsManquants({
      Constat: detail.constat,
      Reproductibilité: detail.reproductibilite,
      Impact: detail.impact,
      'Cause probable': detail.causeProbable,
      'À corriger': detail.aCorriger,
      'Hors périmètre': detail.horsPerimetre,
      'Trouvé dans': detail.trouveDans,
      Contexte: detail.contexte,
      Date: detail.date,
      Priorité: detail.priorite,
    });

    const slug = `bug-${issue}`;
    bugs.push({
      issue,
      titre: courant.titre,
      slug,
      href: `/docs/bugs/${slug}`,
      urlIssue: meta.url || `https://github.com/UlyssouLV/BBASS-Agents-IA/issues/${issue}`,
      complet: manques.length === 0,
      manques,
      resume: tronquer(detail.constat),
      ...detail,
      corpsBrut: corps,
    });
  }
  return bugs;
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

function ecrireIndex() {
  const content = `---
sidebar_label: "Sommaire"
sidebar_position: 0
---

# Bugs connus

import BugsConnusAccueil from '@site/src/components/BugsConnusAccueil';

<BugsConnusAccueil />
`;
  fs.writeFileSync(path.join(OUT_DIR, 'index.mdx'), content, 'utf8');
}

function ecrirePages(bugs) {
  resetOutDir();
  ecrireIndex();
  bugs.forEach((b, index) => {
    const manquesLigne =
      b.manques.length > 0
        ? `\n\n_Informations manquantes : ${b.manques.join(' · ')}_\n`
        : '\n';

    const content = `---
sidebar_label: ${escapeYaml(`#${b.issue}`)}
sidebar_position: ${index + 1}
---

# Bug — ${escapeMdx(b.titre)}

[#${b.issue}](${b.urlIssue})${manquesLigne}

## Constat

${escapeMdx(b.constat)}

## Reproductibilité

${escapeMdx(b.reproductibilite)}

## Impact

${escapeMdx(b.impact)}

## Cause probable

${escapeMdx(b.causeProbable)}

## À corriger

${escapeMdx(b.aCorriger)}

## Hors périmètre

${escapeMdx(b.horsPerimetre)}

## Métadonnées

- Trouvé dans : ${escapeMdx(b.trouveDans)}
- Contexte : ${escapeMdx(b.contexte)}
- Date : ${escapeMdx(b.date)}
- Priorité : ${escapeMdx(b.priorite)}
`;
    fs.writeFileSync(path.join(OUT_DIR, `${b.slug}.md`), content, 'utf8');
  });
}

function main() {
  fs.mkdirSync(path.dirname(OUT_JSON), {recursive: true});
  if (!fs.existsSync(SOURCE)) {
    console.warn('[bugs] fichier introuvable:', SOURCE);
    fs.writeFileSync(OUT_JSON, `${JSON.stringify({bugs: []}, null, 2)}\n`);
    return;
  }
  const markdown = fs.readFileSync(SOURCE, 'utf8');
  const bugs = parserBugs(markdown);
  ecrirePages(bugs);
  const payload = {
    bugs: bugs.map(
      ({
        issue,
        titre,
        slug,
        href,
        urlIssue,
        complet,
        manques,
        resume,
        priorite,
        trouveDans,
        date,
      }) => ({
        issue,
        titre,
        slug,
        href,
        urlIssue,
        complet,
        manques,
        resume,
        priorite,
        trouveDans,
        date,
      }),
    ),
  };
  fs.writeFileSync(OUT_JSON, `${JSON.stringify(payload, null, 2)}\n`, 'utf8');
  console.log(`[bugs] ${bugs.length} bug(s) → JSON + docs/bugs/`);
}

main();
