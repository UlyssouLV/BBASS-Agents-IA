/**
 * Échappement commun aux générateurs de pages (changelog, feuille de route,
 * bugs) : texte inséré dans du MDX, valeur de front matter YAML.
 */

export function escapeMdx(text) {
  return String(text)
    .replace(/\{/g, '\\{')
    .replace(/\}/g, '\\}')
    .replace(/<([\p{L}/])/gu, '\\<$1');
}

export function escapeYaml(value) {
  return JSON.stringify(String(value ?? ''));
}
