const {visit} = require('unist-util-visit');
const {TERMES_GLOSSAIRE} = require('../data/glossaire.cjs');

const IGNORE = new Set([
  'link',
  'linkReference',
  'heading',
  'code',
  'inlineCode',
  'definition',
  'mdxJsxTextElement',
  'mdxJsxFlowElement',
]);

function escapeRegex(texte) {
  return texte.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

const formes = TERMES_GLOSSAIRE.flatMap((terme) => terme.formes);
const MOTIF = new RegExp(
  `(?<![\\p{L}])(?:${formes.map(escapeRegex).join('|')})(?![\\p{L}])`,
  'giu',
);

function slugPour(forme) {
  const cible = forme.toLocaleLowerCase('fr');
  for (const terme of TERMES_GLOSSAIRE) {
    if (terme.formes.some((f) => f.toLocaleLowerCase('fr') === cible)) {
      return terme.slug;
    }
  }
  return null;
}

/** @returns {import('unified').Transformer} */
function remarkGlossaire() {
  return (arbre, fichier) => {
    const chemin = String(fichier.path || (fichier.history && fichier.history[0]) || '');
    if (chemin.replace(/\\/g, '/').includes('/glossaire')) {
      return;
    }

    visit(arbre, 'text', (noeud, index, parent) => {
      if (index === undefined || !parent || IGNORE.has(parent.type)) {
        return;
      }

      const texte = noeud.value;
      MOTIF.lastIndex = 0;
      if (!MOTIF.test(texte)) {
        return;
      }
      MOTIF.lastIndex = 0;

      const morceaux = [];
      let curseur = 0;
      let match;
      while ((match = MOTIF.exec(texte)) !== null) {
        if (match.index > curseur) {
          morceaux.push({type: 'text', value: texte.slice(curseur, match.index)});
        }
        const forme = match[0];
        const slug = slugPour(forme);
        if (slug) {
          const terme = TERMES_GLOSSAIRE.find((t) => t.slug === slug);
          morceaux.push({
            type: 'link',
            url: `/docs/glossaire#${slug}`,
            title: terme ? terme.resume : null,
            children: [{type: 'text', value: forme}],
            data: {
              hProperties: {
                className: 'glossary-term',
              },
            },
          });
        } else {
          morceaux.push({type: 'text', value: forme});
        }
        curseur = match.index + forme.length;
      }
      if (curseur < texte.length) {
        morceaux.push({type: 'text', value: texte.slice(curseur)});
      }

      parent.children.splice(index, 1, ...morceaux);
      return index + morceaux.length;
    });
  };
}

module.exports = remarkGlossaire;
