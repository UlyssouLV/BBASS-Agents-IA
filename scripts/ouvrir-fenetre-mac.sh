# A sourcer (pas executer) : definit la fonction ouvrir_fenetre_mac.
# ouvrir_fenetre_mac "commande a executer" "dossier de travail"
# Ouvre une nouvelle fenetre Terminal.app qui se place dans le dossier puis lance la commande ;
# la fenetre reste ouverte (shell interactif) une fois la commande terminee, pour lire les erreurs.
ouvrir_fenetre_mac() {
    local commande="$1"
    local dossier="$2"
    local tmp="${TMPDIR:-/tmp}/bbass-lancement-$$-$RANDOM.command"
    {
        echo "#!/usr/bin/env bash"
        printf 'cd %q\n' "$dossier"
        echo "$commande"
        echo 'echo'
        echo 'echo "[Processus termine. Ferme cette fenetre ou Ctrl+C.]"'
        echo 'exec "${SHELL:-/bin/bash}"'
    } > "$tmp"
    chmod +x "$tmp"
    open "$tmp"
    return 0
}
