from sqlalchemy import create_engine, inspect, text

from vm_centrale.database import init_db

# Pas de framework de migration (spec 1.4.1) : une base créée avant une
# colonne la reçoit au démarrage, avec la valeur des lignes existantes.


def test_une_base_existante_demarre_avec_la_colonne_provenance(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'ancienne.db'}")
    with engine.begin() as connexion:
        # Table resultats_recherche_web telle que la 1.4.0 l'a créée.
        connexion.execute(
            text(
                "CREATE TABLE resultats_recherche_web ("
                "id INTEGER PRIMARY KEY, conversation_id INTEGER, message_id INTEGER, "
                "requete VARCHAR, url VARCHAR, titre VARCHAR, extrait_moteur VARCHAR, "
                "texte_nettoye VARCHAR, date_creation DATETIME)"
            )
        )
        connexion.execute(
            text(
                "INSERT INTO resultats_recherche_web VALUES "
                "(1, 1, NULL, 'bornage', 'https://a.fr', 'A', 'Extrait', '', '2026-10-01 10:00:00')"
            )
        )

    init_db(engine)
    init_db(engine)

    colonnes = {colonne["name"] for colonne in inspect(engine).get_columns("resultats_recherche_web")}
    assert "provenance" in colonnes
    with engine.connect() as connexion:
        assert connexion.execute(text("SELECT provenance FROM resultats_recherche_web")).scalar_one() == "recherche"
