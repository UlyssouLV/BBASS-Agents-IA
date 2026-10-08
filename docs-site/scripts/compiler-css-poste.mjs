/**
 * Compile la feuille Tailwind du poste pour l'injecter dans les aperçus
 * (cadre isolé). Ne passe pas par le bundle Docusaurus : cette feuille
 * ne doit pas s'appliquer au menu ni au texte du site.
 */
import { createRequire } from 'node:module';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ici = path.dirname(fileURLToPath(import.meta.url));
const poste = path.resolve(ici, '../../poste/frontend');
const entree = path.join(poste, 'src/index.css');
const sortie = path.resolve(ici, '../src/poste/cadreCss.js');
const require = createRequire(path.join(poste, 'package.json'));

const { compile } = require('tailwindcss');
const { Scanner } = require('@tailwindcss/oxide');

const source = fs.readFileSync(entree, 'utf8');

const compiler = await compile(source, {
  base: path.dirname(entree),
  from: entree,
  async loadStylesheet(id, base) {
    const resolu = id.startsWith('.')
      ? path.resolve(base, id)
      : require.resolve(id.endsWith('.css') ? id : `${id}/index.css`);
    return {
      path: resolu,
      base: path.dirname(resolu),
      content: fs.readFileSync(resolu, 'utf8'),
    };
  },
});

const sources = [
  ...compiler.sources.map((sourceCss) => ({
    base: sourceCss.base,
    pattern: sourceCss.pattern,
    negated: sourceCss.negated,
  })),
  {
    base: path.join(poste, 'src'),
    pattern: '**/*.{tsx,ts,jsx,js,html}',
    negated: false,
  },
];

const scanner = new Scanner({ sources });

const candidats = scanner.scan();
let css = compiler.build(candidats);

// La police est déjà chargée par le site de doc. Une url() relative
// dans une balise <style> pointerait vers la page, pas vers le fichier.
css = css.replace(/@font-face\s*\{[^}]*\}/g, '');

// Dans le shadow DOM, :root et body ne sont pas la page du site.
css = css.replaceAll(':root', ':host');
css = css.replace(/(^|\n)(body)(?=\s*\{)/g, '$1:host');

// @property (inherits: false) ne fournit pas sa valeur initiale dans un
// shadow root. Sans ce repli, border-style: var(--tw-border-style) est
// invalide et les champs perdent leur contour. Le bloc est déjà dans
// @layer properties : une classe comme border-dashed peut encore l'écraser.
css = css.replace(
  /@layer properties \{\s*@supports [\s\S]*?\{\s*(\*, ::before, ::after, ::backdrop \{[\s\S]*?\})\s*\}\s*\}/,
  '@layer properties {\n  $1\n}',
);

css += `
:host {
  display: block;
  font-family: Manrope, ui-sans-serif, system-ui, "Segoe UI", sans-serif;
  line-height: 1.5;
}
:host p { margin: 0.35rem 0; }
:host ul { margin: 0.4rem 0 0; padding-left: 1.2rem; }
:host a { color: var(--accent); }
:host code {
  font-family: ui-monospace, Consolas, monospace;
  font-size: 0.85em;
  background: var(--muted);
  padding: 0.1em 0.35em;
  border-radius: 0.25rem;
}
:host pre code { background: none; padding: 0; }
`;

fs.mkdirSync(path.dirname(sortie), { recursive: true });
fs.writeFileSync(sortie, `const css = ${JSON.stringify(css)};\nexport default css;\n`);
console.log(`cadreCss.js : ${css.length} octets, ${candidats.length} classes`);
