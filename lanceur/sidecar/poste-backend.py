# Point d'entrée PyInstaller du backend poste (sidecar du Lanceur, ADR-0022).
# Figé, le backend passe en mode paquet (poste.config.EN_MODE_PAQUET).
from poste.main import run

if __name__ == "__main__":
    run()
