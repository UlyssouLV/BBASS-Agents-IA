from pathlib import Path

from mistral_common.tokens.tokenizers.base import Tokenizer
from mistral_common.tokens.tokenizers.mistral import MistralTokenizer

from vm_centrale.config import FICHES_MODELES

_DOSSIER_TOKENIZERS = Path(__file__).parent / "tokenizers"

# Un chargement par fichier et par processus (plusieurs secondes pour un
# fichier de 16 Mo) : les démarrages suivants, dans les tests, le reprennent.
_tokenizers: dict[Path, Tokenizer] = {}


def _chemin(modele: str) -> Path:
    fichier = FICHES_MODELES[modele].fichier_tokenizer
    if fichier is None:
        raise ValueError(f"Aucun tokenizer déclaré pour le modèle {modele}")
    return _DOSSIER_TOKENIZERS / fichier


def _charger(chemin: Path) -> Tokenizer:
    if chemin not in _tokenizers:
        _tokenizers[chemin] = MistralTokenizer.from_file(str(chemin)).instruct_tokenizer.tokenizer
    return _tokenizers[chemin]


def charger_tokenizers() -> None:
    # Au démarrage (spec 1.4.2) : chaque fiche qui déclare un tokenizer le
    # charge ; un échec lève et empêche la VM de démarrer, pour qu'un plafond
    # faux ne passe jamais inaperçu.
    for modele, fiche in FICHES_MODELES.items():
        if fiche.fichier_tokenizer is not None:
            _charger(_chemin(modele))


def compter_tokens(texte: str, modele: str) -> int:
    # Texte brut, sans les tokens spéciaux d'un message (début, fin, rôle).
    return len(_charger(_chemin(modele)).encode(texte, bos=False, eos=False))
