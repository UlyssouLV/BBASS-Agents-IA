#!/usr/bin/env bash
# Trouve uv sur le PATH, ou dans le dossier d'installation par defaut, ou
# l'installe (script officiel Astral). A sourcer depuis preparer-package.sh
# pour que PATH survive ; executable seul aussi.
ensure_uv() {
    if command -v uv >/dev/null 2>&1; then
        return 0
    fi

    if [[ -x "${HOME}/.local/bin/uv" ]]; then
        export PATH="${HOME}/.local/bin:${PATH}"
        return 0
    fi

    if [[ -x "${HOME}/.cargo/bin/uv" ]]; then
        export PATH="${HOME}/.cargo/bin:${PATH}"
        return 0
    fi

    echo "      uv n'est pas installe : installation (script officiel Astral)..."
    if ! curl -LsSf https://astral.sh/uv/install.sh | sh; then
        echo "[ERREUR] Echec de l'installation de uv." >&2
        echo "         Installe-le a la main (voir README.md, section Prerequis), puis relance ce script." >&2
        return 1
    fi

    export PATH="${HOME}/.local/bin:${PATH}"

    if ! command -v uv >/dev/null 2>&1; then
        echo "[ERREUR] uv a ete installe mais n'est pas sur le PATH de cette fenetre." >&2
        echo "         Ferme cette fenetre, relance le script. Si ca persiste, vois README.md (Prerequis)." >&2
        return 1
    fi

    return 0
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    ensure_uv
    exit $?
fi
