import re

# Le titre est affiché en texte brut (BarreLaterale.tsx), jamais passé par le
# rendu Markdown borné du message assistant (#93) — contrairement à lui, un
# « ** » résiduel dans le titre s'affiche donc littéralement. La consigne du
# prompt de titrage ne suffit pas à elle seule (constaté lors de la
# validation manuelle de la 1.2.2 : le titrage reprend parfois le gras de la
# réponse qu'il résume malgré la consigne) ; ce nettoyage réplique en Python
# le principe déjà appliqué côté poste pour le corps du message : neutraliser
# ce que le modèle produit malgré la consigne plutôt que de ne compter que
# sur elle. Ne s'applique qu'au titre généré par le modèle, jamais à un
# renommage saisi à la main par un collaborateur (PATCH /conversations/{id}).
#
# Chaque motif exige en plus qu'aucun caractère alphanumérique ne touche
# directement les marqueurs par l'extérieur (`(?<!\w)` / `(?!\w)`) : sans
# cette garde, une paire de "*" ou "_" purement incidente (ex. "10*2 et
# 5*3", un calcul ; "mon_profil_travail", un identifiant) est elle aussi
# appariée et son contenu supprimé, alors qu'il ne s'agit pas d'une
# emphase Markdown.
_MARQUEURS_MARKDOWN_TITRE = (
    (re.compile(r"^#{1,6}\s*"), ""),
    (re.compile(r"(?<!\w)\*\*(.+?)\*\*(?!\w)"), r"\1"),
    (re.compile(r"(?<!\w)__(.+?)__(?!\w)"), r"\1"),
    (re.compile(r"(?<!\w)(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)(?!\w)"), r"\1"),
    (re.compile(r"(?<!\w)(?<!_)_(?!_)(.+?)(?<!_)_(?!_)(?!\w)"), r"\1"),
)


def nettoyer_titre(titre: str) -> str:
    titre = titre.strip()
    for motif, remplacement in _MARQUEURS_MARKDOWN_TITRE:
        titre = motif.sub(remplacement, titre)
    return titre.strip()
