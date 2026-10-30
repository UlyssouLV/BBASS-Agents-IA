// Issue #272 (spec 1.6.3, point 10) : pendant la frappe, le texte déjà
// révélé passe par le rendu Markdown habituel à chaque étape. Coupé au
// hasard, il laisserait voir des marqueurs bruts (`**gras`, `[lien](htt`,
// `| ligne de tableau`, clôture de bloc de code à moitié tapée). Cette
// fonction complète le texte pour l'affichage seulement : marqueurs ouverts
// refermés, ligne de tableau, lien ou ouverture de bloc de code incomplets
// retenus jusqu'à leur fin. Le texte stocké n'est jamais modifié, et un
// texte complet n'est pas passé ici (rendu final identique).

// Une barrière en accents graves n'a aucun autre accent grave sur sa ligne :
// « ```npm install``` » est du code en ligne (CommonMark).
const _BARRIERE_BLOC_CODE = /^ {0,3}(`{3,}(?=[^`]*$)|~{3,})/;
// Préfixe de bloc d'une ligne (puce, numéro, titre, citation) : ses `*` ne
// sont pas des marqueurs d'emphase.
const _PREFIXE_DE_BLOC = /^\s*(?:(?:[-*+]|\d+[.)])\s+|#{1,6}\s+|>\s*)*/;
// Lien ou image encore incomplet en fin de ligne : `[texte`, `[texte]`
// (peut encore devenir un lien) ou `[texte](url`.
const _LIEN_INCOMPLET = /^!?\[[^\]]*(?:\](?:\([^)]*)?)?$/;

function estAlphanumerique(caractere: string | undefined): boolean {
  return caractere !== undefined && /[\p{L}\p{N}]/u.test(caractere);
}

function longueurDeSerie(texte: string, debut: number): number {
  let fin = debut;
  while (texte[fin] === texte[debut]) {
    fin++;
  }
  return fin - debut;
}

// Marqueurs d'emphase et de code en ligne restés ouverts, dans l'ordre
// d'ouverture.
function marqueursOuverts(ligne: string): string[] {
  const pile: string[] = [];
  let i = _PREFIXE_DE_BLOC.exec(ligne)?.[0].length ?? 0;
  while (i < ligne.length) {
    const caractere = ligne[i];
    if (caractere === "\\") {
      i += 2;
      continue;
    }
    if (caractere !== "`" && caractere !== "*" && caractere !== "_" && caractere !== "~") {
      i++;
      continue;
    }
    const serie = caractere.repeat(longueurDeSerie(ligne, i));
    if (caractere === "`") {
      const fermeture = ligne.indexOf(serie, i + serie.length);
      if (fermeture === -1) {
        // Le reste de la ligne est du code : rien d'autre à refermer dedans.
        pile.push(serie);
        break;
      }
      i = fermeture + serie.length;
      continue;
    }
    const avant = ligne[i - 1];
    const apres = ligne[i + serie.length];
    const intraMot = caractere === "_" && estAlphanumerique(avant) && estAlphanumerique(apres);
    if (intraMot || (caractere === "~" && serie.length < 2)) {
      // snake_case, ~ isolé : texte, pas un marqueur.
    } else if (pile.at(-1)?.[0] === caractere) {
      pile.pop();
    } else if (apres !== undefined && !/\s/.test(apres)) {
      pile.push(serie);
    }
    i += serie.length;
  }
  return pile;
}

// Ligne en cours de frappe (hors bloc de code) : texte affichable, ou ""
// tant qu'elle doit être retenue.
function completerLigneEnCours(ligne: string): string {
  const debut = ligne.trimStart();
  if (debut.startsWith("|") || /^(`{1,2}|~{1,2})$/.test(debut) || _BARRIERE_BLOC_CODE.test(ligne)) {
    return "";
  }
  let texte = ligne;
  const crochet = texte.lastIndexOf("[");
  if (crochet !== -1) {
    const debutLien = texte[crochet - 1] === "!" ? crochet - 1 : crochet;
    if (_LIEN_INCOMPLET.test(texte.slice(debutLien))) {
      texte = texte.slice(0, debutLien);
    }
  }
  // Un marqueur en toute fin peut être le début d'un `**` ou d'une
  // fermeture : retiré, puis les marqueurs encore ouverts sont refermés.
  texte = texte.replace(/[\s*_~`]+$/, "");
  // Puce, numéro ou titre encore vide : rien à afficher (sous un paragraphe,
  // un `-` seul serait lu comme un soulignement de titre).
  if (!/[\p{L}\p{N}]/u.test(texte) || /^\s*\d+[.)]?$/.test(texte)) {
    return "";
  }
  return texte + marqueursOuverts(texte).reverse().join("");
}

export function markdownEnCoursDeFrappe(texteRevele: string): string {
  const lignes = texteRevele.split("\n");
  const ligneEnCours = lignes.pop() ?? "";

  let barriereOuverte: string | null = null;
  for (const ligne of lignes) {
    const barriere = _BARRIERE_BLOC_CODE.exec(ligne)?.[1];
    if (barriere === undefined) {
      continue;
    }
    if (barriereOuverte === null) {
      barriereOuverte = barriere;
    } else if (
      barriere[0] === barriereOuverte[0] &&
      barriere.length >= barriereOuverte.length &&
      ligne.trim() === barriere
    ) {
      barriereOuverte = null;
    }
  }

  if (barriereOuverte !== null) {
    // Dans un bloc de code : son contenu s'affiche tel quel, mais une ligne
    // qui commence comme sa clôture est retenue, puis le bloc est refermé.
    const gardeLigne = ligneEnCours !== "" && !ligneEnCours.trimStart().startsWith(barriereOuverte[0]);
    return [...lignes, ...(gardeLigne ? [ligneEnCours] : []), barriereOuverte].join("\n");
  }

  const ligneAffichee = completerLigneEnCours(ligneEnCours);
  if (ligneAffichee === "") {
    // Un en-tête de tableau sans sa ligne de séparation s'afficherait comme
    // un paragraphe de `|` : retenu jusqu'à ce qu'elle soit complète.
    let debutTableau = lignes.length;
    while (debutTableau > 0 && lignes[debutTableau - 1].trimStart().startsWith("|")) {
      debutTableau--;
    }
    if (lignes.length - debutTableau === 1) {
      lignes.length = debutTableau;
    }
  }
  return [...lignes, ligneAffichee].join("\n");
}
