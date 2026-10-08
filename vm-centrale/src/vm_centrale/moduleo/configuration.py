import logging
from dataclasses import dataclass, field

from vm_centrale.config import get_config_moduleo_chiffree
from vm_centrale.secrets_chiffres import SecretIndechiffrable, dechiffrer, lire_cle_maitre

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ConfigModuleo:
    url: str
    # repr=False : une config journalisée ou affichée dans une trace ne
    # montre jamais les secrets (ADR-0017).
    api_key: str = field(repr=False)
    security_code: str = field(repr=False)


def config_moduleo() -> ConfigModuleo | None:
    # Seul point qui dit si Moduléo est configuré (spec 1.5.0, #173) : None
    # quand une variable manque ou qu'un secret ne se déchiffre pas, sans
    # lever, pour que la VM démarre et que les outils Moduléo ne soient
    # simplement pas proposés. Les logs nomment la variable en cause, jamais
    # une valeur.
    brute = get_config_moduleo_chiffree()
    url, fichier_cle_maitre = brute.url, brute.fichier_cle_maitre
    chiffrees = {
        "MODULEO_API_KEY_CHIFFREE": brute.api_key_chiffree,
        "MODULEO_SECURITY_CODE_CHIFFRE": brute.security_code_chiffre,
    }
    manquantes = [
        nom
        for nom, valeur in (("MODULEO_URL", url), *chiffrees.items(), ("VM_CLE_MAITRE_FICHIER", fichier_cle_maitre))
        if valeur is None
    ]
    if url is None or fichier_cle_maitre is None or manquantes:
        logger.warning("Moduléo non configuré : %s manquant(s) dans .env.", ", ".join(manquantes))
        return None
    try:
        cle_maitre = lire_cle_maitre(fichier_cle_maitre)
    except OSError as erreur:
        logger.warning(
            "Moduléo non configuré : clé maître %s illisible (%s).", fichier_cle_maitre, type(erreur).__name__
        )
        return None
    secrets: dict[str, str] = {}
    for nom, valeur_chiffree in chiffrees.items():
        try:
            # `or ""` pour le typage : `manquantes` vide garantit la valeur.
            secrets[nom] = dechiffrer(valeur_chiffree or "", cle_maitre)
        except SecretIndechiffrable:
            logger.warning(
                "Moduléo non configuré : %s ne se déchiffre pas avec la clé maître %s.", nom, fichier_cle_maitre
            )
            return None
    logger.info("Moduléo configuré sur %s.", url)
    return ConfigModuleo(
        url=url,
        api_key=secrets["MODULEO_API_KEY_CHIFFREE"],
        security_code=secrets["MODULEO_SECURITY_CODE_CHIFFRE"],
    )
