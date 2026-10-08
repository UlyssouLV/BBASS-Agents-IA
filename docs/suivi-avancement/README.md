# Suivi d’avancement — standards

Bilan HTML (+ PDF) de la semaine de travail cabinet, sous `docs/suivi-avancement/`.

Outils branchés dessus :

- skill `/os` (`ouvrir-semaine-de-travail`) — crée le dossier + HTML de la semaine ;
- skill `/msa` (`mettre-a-jour-suivi-avancement`) — enregistre une version livrée + régénère le PDF ;
- skill **Finalise la version** — appelle `/msa` (soft-skip s’il n’y a pas de semaine) ;
- script `generer-pdf.mjs` — resync agenda puis Chrome / Edge headless ;
- script `sync-agenda.mjs` — lit l’Excel de la semaine dans le dossier externe **Suivi** → `agenda-quotidien-tableau.png` + section HTML ;
- script `docs-site/scripts/capturer-travail-realise.mjs` — aperçu README (lit le HTML de la semaine courante).

Rôle agents : **`suivi-avancement`** → `docs/suivi-avancement/` (`agents/roles.yml`).

## Semaine = lundi → vendredi

Fuseau : **Europe/Paris**. Une semaine de travail = lun–ven (pas la semaine ISO dimanche).

### Noms (nouvelles semaines)

| Élément | Motif | Exemple |
| --- | --- | --- |
| Dossier | `semaine-<lun>-<ven>-<mois>-<année>` | `semaine-05-09-oct-2026` |
| HTML | `suivi-semaine-<lun>-<ven>-<mois>-<année>.html` | mêmes dates que le dossier |
| PDF | même base que le HTML, `.pdf` | à côté du HTML |

Mois du dossier (ASCII, comme `capturer-travail-realise.mjs`) : `jan` `fev` `mar` `avr` `mai` `juin` `juil` `aout` `sept` `oct` `nov` `dec`.

**Historique** : ne pas renommer les anciennes semaines. Lecture souple : dans un dossier, le premier `suivi-semaine-*.html` compte (même si le suffixe ne matche pas parfaitement le dossier).

## Fichiers à la racine de ce dossier

| Fichier | Rôle |
| --- | --- |
| `README.md` | cette convention |
| `template-semaine.html` | gabarit canonique (CSS + structure) pour `/os` |
| `generer-pdf.mjs` | sync agenda + régénération PDF |
| `sync-agenda.mjs` | Excel Suivi → PNG + `#agenda-quotidien` |
| `xlsx-vers-html-agenda.py` | helper openpyxl (appelé par sync-agenda) |

## Emploi du temps (agenda)

Source **hors repo** : dossier sibling `../Suivi` (ou `BBASS_SUIVI_DIR`).

| Repo (`docs/suivi-avancement/`) | Suivi externe |
| --- | --- |
| `semaine-05-09-oct-2026` (lundi = 05/10/2026) | `Semaine du 05-10-26/` + `Semaine *.xlsx` |

`sync-agenda.mjs` (et donc `generer-pdf.mjs`) retrouve le dossier par la **date du lundi**, prend le premier `Semaine*.xlsx` (sinon `*.xlsx`), régénère `agenda-quotidien-tableau.png` et remplace le contenu de `#agenda-quotidien`. Soft-skip si Suivi / Excel absent (placeholder conservé). `--strict` pour échouer.

## Structure HTML obligatoire

Reprendre **`template-semaine.html`**. Sections attendues :

1. **Couverture** — logo, titre, dates, liens **Dépôt** (GitHub) + **Documentation technique** (GitHub Pages : `https://ulyssoulv.github.io/BBASS-Agents-IA/`), badge semaine, **TOC**.
2. **`#travail-realise`** — un `.jour` par jour lun→ven ; puces en **langage fonctionnel** (cabinet) : pas de noms d’outils/stack, pas de `#ticket` dans les puces jour.
3. **`#reste-a-implementer`** — suite feuille de route / non livré.
4. **`#livre-pour`** — récap point (visé / livré), langage fonctionnel.
5. **`#descriptif-versions`** — blocs `.version` avec `id="version-X-Y-Z"` :
   - prévu : `<span class="prevu">…</span>` ;
   - livré : `<span class="deploye">Déployé le JJ/MM/AAAA à HH:MM</span>` + corps enrichi.
6. **`#agenda-quotidien`** — PNG synchronisé depuis Suivi (voir ci-dessus) ; placeholder tant que sync n’a pas tourné.
7. TOC : entrée par version sous « Descriptif des versions » + entrée agenda.

Slots `data-slot="…"` dans le template = repères pour les skills ; on peut les retirer une fois le HTML rempli.

## PDF

```bash
node docs/suivi-avancement/generer-pdf.mjs docs/suivi-avancement/semaine-JJ-JJ-mois-AAAA/
# ou chemin direct vers le .html
```

- Navigateur : Chrome ou Edge (chemins usuels Windows / macOS / Linux).
- Options : `--headless=new --no-pdf-header-footer --print-to-pdf=…`.
- Si le PDF est **ouvert** ailleurs → erreur claire « verrouillé » : fermer puis relancer.
- Ne pas inventer une autre commande dans un skill : toujours ce script.

## Qui appelle quoi

| Moment | Action |
| --- | --- |
| Début de semaine (ou avant la 1ʳᵉ finalisation de la semaine) | **`/os`** — crée dossier + HTML (attendus = Prochaine/Ensuite roadmap, surcharge possible dans le prompt) |
| À chaque **Finalise la version** | **`/msa`** (via finaliser) — met à jour le HTML pour `X.Y.Z`, régénère le PDF |
| Pas de dossier pour la semaine courante à la finalisation | **soft-skip** + rappel de lancer `/os` ; on ne bloque pas le release |
| Commit / push | **ni `/os` ni `/msa`** — via `/c` (finaliser fait `/c -a -p` sur le lot docs) |

## Langage

Public = lecteur cabinet. Dans les puces jour et le corps des `.version` : bénéfices et comportements visibles, pas d’implémentation, pas d’IDs GitHub.
