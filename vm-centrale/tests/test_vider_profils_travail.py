import importlib.util
from datetime import datetime
from pathlib import Path

from vm_centrale.models import ProfilTravail

_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "vider_profils_travail.py"


def _charger_script():
    spec = importlib.util.spec_from_file_location("vider_profils_travail", _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_le_script_vide_tous_les_profils(client, jeton_valide, jeton_store, db_session):
    # Profils hérités de la concaténation, potentiellement contaminés
    # (spec 1.3.1) : tous vidés une fois.
    for identifiant in ("j.dupont", "n.durand"):
        db_session.add(
            ProfilTravail(
                identifiant_compte=identifiant,
                contenu="Aime les liens PDF.\nAime les liens PDF.",
                date_derniere_maj=datetime(2026, 10, 1),
            )
        )
    db_session.commit()

    _charger_script().vider(db_session)

    for identifiant, jeton in (("j.dupont", jeton_valide), ("n.durand", jeton_store.emettre("n.durand"))):
        reponse = client.get(
            f"/comptes/{identifiant}/profil-travail", headers={"Authorization": f"Bearer {jeton}"}
        )
        assert reponse.json()["contenu"] == ""
