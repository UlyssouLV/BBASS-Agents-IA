/**
 * Compte les commits sur main + la somme des commits des PR mergées
 * (historique des branches squashées), puis met à jour le README
 * entre <!-- sync:stats-commits --> … <!-- /sync:stats-commits -->.
 *
 * Env : GITHUB_TOKEN (optionnel en local via `gh`), GITHUB_REPOSITORY (owner/repo).
 *
 * Usage : node scripts/generer-stats-commits.mjs
 */
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {execFileSync} from 'node:child_process';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(__dirname, '../..');
const README = path.join(REPO_ROOT, 'README.md');
const START = '<!-- sync:stats-commits -->';
const END = '<!-- /sync:stats-commits -->';

function repoSlug() {
  if (process.env.GITHUB_REPOSITORY) return process.env.GITHUB_REPOSITORY;
  try {
    const url = execFileSync('git', ['remote', 'get-url', 'origin'], {
      cwd: REPO_ROOT,
      encoding: 'utf8',
    }).trim();
    const m = url.match(/github\.com[:/](.+?)(?:\.git)?$/i);
    if (m) return m[1].replace(/\\/g, '/');
  } catch {
    /* ignore */
  }
  return 'UlyssouLV/BBASS-Agents-IA';
}

function token() {
  if (process.env.GITHUB_TOKEN || process.env.GH_TOKEN) {
    return process.env.GITHUB_TOKEN || process.env.GH_TOKEN;
  }
  try {
    return execFileSync('gh', ['auth', 'token'], {
      encoding: 'utf8',
      stdio: ['ignore', 'pipe', 'ignore'],
    }).trim();
  } catch {
    return '';
  }
}

async function ghJson(pathname, {raw = false} = {}) {
  const headers = {
    Accept: 'application/vnd.github+json',
    'X-GitHub-Api-Version': '2022-11-28',
    'User-Agent': 'bbass-stats-commits',
  };
  const t = token();
  if (t) headers.Authorization = `Bearer ${t}`;
  const res = await fetch(`https://api.github.com${pathname}`, {headers});
  if (!res.ok) {
    throw new Error(`${pathname} → ${res.status} ${await res.text()}`);
  }
  if (raw) return res;
  return res.json();
}

function parseLastPage(linkHeader) {
  if (!linkHeader) return 1;
  const m = linkHeader.match(/[?&]page=(\d+)>;\s*rel="last"/);
  return m ? Number(m[1]) : 1;
}

async function commitsSurMain(owner, repo) {
  const res = await ghJson(
    `/repos/${owner}/${repo}/commits?sha=main&per_page=1`,
    {raw: true},
  );
  await res.arrayBuffer();
  return parseLastPage(res.headers.get('link'));
}

async function prsMergees(owner, repo) {
  const out = [];
  let page = 1;
  for (;;) {
    const batch = await ghJson(
      `/repos/${owner}/${repo}/pulls?state=closed&per_page=100&page=${page}`,
    );
    if (!batch.length) break;
    for (const pr of batch) {
      if (pr.merged_at) out.push(pr.number);
    }
    if (batch.length < 100) break;
    page += 1;
  }
  return out;
}

async function commitsDunePr(owner, repo, number) {
  const pr = await ghJson(`/repos/${owner}/${repo}/pulls/${number}`);
  return Number(pr.commits) || 0;
}

function blocMarkdown({main, prs, owner, repo}) {
  const badgeMain = `https://img.shields.io/badge/commits_main-${main}-c8102e?style=for-the-badge`;
  const badgePrs = `https://img.shields.io/badge/commits_PR_(historique)-${prs}-1e3a5f?style=for-the-badge`;
  const activity = `https://img.shields.io/github/commit-activity/y/${owner}/${repo}?style=for-the-badge&color=c8102e&label=activit%C3%A9`;
  return `${START}
<p align="center">
  <img src="${badgeMain}" alt="${main} commits sur main" />
  <img src="${badgePrs}" alt="${prs} commits dans les PR mergées" />
  <img src="${activity}" alt="Activité de commits sur un an" />
</p>
${END}`;
}

function majReadme(bloc) {
  let readme = fs.readFileSync(README, 'utf8');
  if (!readme.includes(START) || !readme.includes(END)) {
    throw new Error(`Marqueurs manquants dans README.md (${START} … ${END}).`);
  }
  const pattern = new RegExp(
    `${escapeRegExp(START)}[\\s\\S]*?${escapeRegExp(END)}`,
  );
  const apres = readme.replace(pattern, bloc);
  if (apres === readme) {
    console.log('[stats] README déjà à jour.');
    return false;
  }
  fs.writeFileSync(README, apres, 'utf8');
  console.log('[stats] README mis à jour.');
  return true;
}

function escapeRegExp(s) {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

async function main() {
  const slug = repoSlug();
  const [owner, repo] = slug.split('/');
  console.log(`[stats] dépôt ${owner}/${repo}`);

  const mainCount = await commitsSurMain(owner, repo);
  const numeros = await prsMergees(owner, repo);
  let prCommits = 0;
  for (const n of numeros) {
    prCommits += await commitsDunePr(owner, repo, n);
  }

  console.log(`[stats] main=${mainCount} · PR mergées=${numeros.length} · commits PR=${prCommits}`);
  majReadme(blocMarkdown({main: mainCount, prs: prCommits, owner, repo}));
}

main().catch((e) => {
  console.error('[stats]', e);
  process.exit(1);
});
