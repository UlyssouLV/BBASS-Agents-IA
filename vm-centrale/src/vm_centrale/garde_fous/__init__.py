# Corrections que le code applique à ce que le modèle produit malgré sa
# consigne (spec 1.3.1), un paquet par garde-fou. Index : README.md ;
# règles, appelants et historique : README.md de chaque paquet.
from vm_centrale.garde_fous.chiffres import retirer_chiffres_hors_source
from vm_centrale.garde_fous.contact_non_lu import PHRASE_CONTACT_NON_LU, remplacer_contact_non_lu
from vm_centrale.garde_fous.ecriture_annoncee import (
    PHRASE_CARTE_OUVERTE,
    PHRASE_ECRITURE_NON_PROPOSEE,
    affirme_une_ecriture,
    annonce_une_carte,
    retirer_ecriture_affirmee,
)
from vm_centrale.garde_fous.longueur import plafonner
from vm_centrale.garde_fous.pages_trop_longues import mentionner_pages_trop_longues
from vm_centrale.garde_fous.refus_des_droits import montrer_refus_des_droits
from vm_centrale.garde_fous.sources import LectureSource, PageSource, ajouter_sources
from vm_centrale.garde_fous.titre import nettoyer_titre
from vm_centrale.garde_fous.urls import normaliser_url, retirer_urls_inventees, urls_ecrites

__all__ = [
    "LectureSource",
    "PHRASE_CARTE_OUVERTE",
    "PHRASE_CONTACT_NON_LU",
    "PHRASE_ECRITURE_NON_PROPOSEE",
    "PageSource",
    "affirme_une_ecriture",
    "ajouter_sources",
    "annonce_une_carte",
    "mentionner_pages_trop_longues",
    "montrer_refus_des_droits",
    "nettoyer_titre",
    "normaliser_url",
    "plafonner",
    "remplacer_contact_non_lu",
    "retirer_ecriture_affirmee",
    "retirer_chiffres_hors_source",
    "retirer_urls_inventees",
    "urls_ecrites",
]
