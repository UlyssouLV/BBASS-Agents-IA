# Outils que le modèle peut décider d'appeler (tool calling), sur l'appel de
# chat principal seulement (spec 1.4.0). Inventaire et éligibilité :
# README.md.
from vm_centrale.outils.base import AppelMistralOutil, ContexteTour, ResultatOutil
from vm_centrale.outils.registre import executer_appel, outils_du_tour

__all__ = [
    "AppelMistralOutil",
    "ContexteTour",
    "ResultatOutil",
    "executer_appel",
    "outils_du_tour",
]
