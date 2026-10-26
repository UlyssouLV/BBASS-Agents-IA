# Suivi d’avancement — standards

Bilan HTML (+ PDF optionnel) de la semaine de travail, sous `docs/suivi-avancement/`.

Opt-in : rôle **`suivi-avancement`** ajouté à `/init` (o) ou `adopter-le-pack.sh --with-suivi`. Sans ce rôle, Finalise soft-skip `/msa`.

Outils branchés dessus :

- skill `/os` (`ouvrir-semaine-de-travail`) — crée le dossier + HTML de la semaine ;
- skill `/msa` (`mettre-a-jour-suivi-avancement`) — enregistre une version livrée + régénère le PDF si `generer-pdf.mjs` existe ;
- skill **Finalise la version** — appelle `/msa` quand le rôle est résolu (soft-skip sinon / s’il n’y a pas de semaine).

Rôle agents : **`suivi-avancement`** → `docs/suivi-avancement/` (`agents/roles.yml`).

## Semaine = lundi → vendredi

Fuseau : **Europe/Paris**. Une semaine de travail = lun–ven (pas la semaine ISO dimanche).

### Noms (nouvelles semaines)

| Élément | Motif | Exemple |
| --- | --- | --- |
| Dossier | `semaine-<lun>-<ven>-<mois>-<année>` | `semaine-05-09-oct-2026` |
| HTML | `suivi-semaine-<lun>-<ven>-<mois>-<année>.html` | mêmes dates que le dossier |
| PDF | même base que le HTML, `.pdf` | à côté du HTML (si script PDF présent) |

Mois du dossier (ASCII) : `jan` `fev` `mar` `avr` `mai` `juin` `juil` `aout` `sept` `oct` `nov` `dec`.

**Historique** : ne pas renommer les anciennes semaines. Lecture souple : dans un dossier, le premier `suivi-semaine-*.html` compte.

## Fichiers à la racine de ce dossier

| Fichier | Rôle |
| --- | --- |
| `README.md` | cette convention |
| `template-semaine.html` | gabarit canonique (CSS + structure) pour `/os` |
| `generer-pdf.mjs` | **optionnel** — régénération PDF (Chrome / Edge headless) ; `/msa` soft-skip si absent |

## Structure HTML obligatoire

Reprendre **`template-semaine.html`**. Sections attendues :

1. **Couverture** — titre, dates, lien dépôt (placeholder à remplir), badge semaine, **TOC**.
2. **`#travail-realise`** — un `.jour` par jour lun→ven ; puces en **langage fonctionnel produit** : pas de noms d’outils/stack, pas de `#ticket` dans les puces jour.
3. **`#reste-a-implementer`** — suite feuille de route / non livré.
4. **`#livre-pour`** — récap point (visé / livré), langage fonctionnel.
5. **`#descriptif-versions`** — blocs `.version` avec `id="version-X-Y-Z"` :
   - prévu : `<span class="prevu">…</span>` ;
   - livré : `<span class="deploye">Déployé le JJ/MM/AAAA à HH:MM</span>` + corps enrichi.
6. TOC : entrée par version sous « Descriptif des versions ».

Slots `data-slot="…"` dans le template = repères pour les skills ; on peut les retirer une fois le HTML rempli.

## PDF (optionnel)

Si `generer-pdf.mjs` est présent :

```bash
node docs/suivi-avancement/generer-pdf.mjs docs/suivi-avancement/semaine-JJ-JJ-mois-AAAA/
```

Sinon `/msa` met à jour le HTML et soft-skip le PDF.

## Qui appelle quoi

| Moment | Action |
| --- | --- |
| Début de semaine (ou avant la 1ʳᵉ finalisation de la semaine) | **`/os`** — crée dossier + HTML (attendus = Prochaine/Ensuite roadmap, surcharge possible dans le prompt) |
| À chaque **Finalise la version** | **`/msa`** (via finaliser, si rôle présent) — met à jour le HTML pour `X.Y.Z`, PDF si script présent |
| Pas de dossier pour la semaine courante à la finalisation | **soft-skip** + rappel de lancer `/os` ; on ne bloque pas le release |
| Commit / push | **ni `/os` ni `/msa`** — via `/c` (finaliser fait `/c -a -p` sur le lot docs) |

## Langage

Public = lecteur produit / métier. Dans les puces jour et le corps des `.version` : bénéfices et comportements visibles, pas d’implémentation, pas d’IDs GitHub.
