# Image épinglée (jamais latest, spec 1.4.0) avec settings.yml copié dedans
# plutôt que monté : Docker Desktop ne voit pas un fichier monté depuis un
# lecteur réseau (dépôt cloné sur H:) et monte un dossier vide à sa place.
FROM searxng/searxng:2026.10.4-d48c4b555
COPY --chown=searxng:searxng settings.yml /etc/searxng/settings.yml
# L'image tourne en root par défaut (Sonar docker:S6471) ; son utilisateur
# searxng possède déjà /etc/searxng et /var/cache/searxng. Seule fonction
# root perdue : update-ca-certificates au démarrage, inutile ici (aucun
# certificat ajouté).
USER searxng
