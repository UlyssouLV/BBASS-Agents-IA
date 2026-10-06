# tokenizers

Tokenizers des modèles Mistral, versionnés dans git (pas de Git LFS), chargés par `compte_tokens.py` au démarrage de la VM. Chaque fiche de modèle (`config.py`) qui déclare un `fichier_tokenizer` pointe ici. Un fichier manquant ou illisible empêche la VM de démarrer. Jamais de téléchargement au démarrage : `mistral-common` ne contient aucun tokenizer plus récent que celui de `mistral-small-2409`.

Ils servent à compter les tokens d'un texte sur la VM (plafond des pages de `rechercher_web`), jamais à ce que reçoit Mistral, qui tokenise de son côté.

| Fichier | Modèle | Source | Révision | Taille | Relevé |
| --- | --- | --- | --- | --- | --- |
| `mistral-small-2603/tekken.json` | `mistral-small-2603` (Mistral Small 4) | Hugging Face [`mistralai/Mistral-Small-4-119B-2603`](https://huggingface.co/mistralai/Mistral-Small-4-119B-2603) | `a11f36bebf709121056b1dbcc943d1c6afbe494d` | 16 275 354 octets, SHA-256 `b1272b956bd6edd2d2c674c76896c7661308c9e723997b0afb55ecb429cb5dc7` | 2026-10-06 |

Changer de modèle : ajouter son tokenizer ici et sa ligne dans ce tableau, dans le même commit que sa fiche.

**Depuis.** 1.4.2 (#146).
