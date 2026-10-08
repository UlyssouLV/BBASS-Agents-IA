from cryptography.fernet import Fernet, InvalidToken


class SecretIndechiffrable(Exception):
    # Clé maître illisible (pas une clé Fernet), fausse, ou valeur chiffrée
    # corrompue. Le message ne contient jamais ni la clé maître ni le secret.
    pass


def lire_cle_maitre(chemin: str) -> bytes:
    # Fichier hors du dépôt (spec 1.5.0, ADR-0017), écrit par
    # scripts/chiffrer_secret.py. Lève OSError s'il est absent ou illisible.
    with open(chemin, "rb") as fichier:
        return fichier.read().strip()


def dechiffrer(valeur_chiffree: str, cle_maitre: bytes) -> str:
    try:
        return Fernet(cle_maitre).decrypt(valeur_chiffree.encode()).decode()
    except (ValueError, InvalidToken) as erreur:
        # ValueError : clé maître qui n'est pas une clé Fernet ; InvalidToken :
        # clé fausse ou valeur corrompue. `from None` : la trace ne garde rien.
        raise SecretIndechiffrable(type(erreur).__name__) from None
