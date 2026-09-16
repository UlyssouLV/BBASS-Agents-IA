"""Seed idempotent d'un compte administrateur de test pour le developpement local.

Appele par lancer-vm.bat / lancer-logiciel.bat a chaque demarrage. Ne touche
jamais a un compte deja existant (ne reinitialise pas son mot de passe) : si
IDENTIFIANT existe deja, ce script se contente de rafficher les identifiants
de connexion supposes (ceux fixes ci-dessous), sans toucher a la base.
"""

from vm_centrale.database import SessionLocal, init_db
from vm_centrale.models import Compte, ComptePole
from vm_centrale.security import hash_password

IDENTIFIANT = "admin"
MOT_DE_PASSE = "ChangeMoi123!"


def main() -> None:
    init_db()
    db = SessionLocal()
    try:
        compte = db.query(Compte).filter(Compte.identifiant == IDENTIFIANT).first()
        cree = compte is None
        if cree:
            db.add(
                Compte(
                    identifiant=IDENTIFIANT,
                    mot_de_passe_hash=hash_password(MOT_DE_PASSE),
                    prenom="Admin",
                    nom="BBASS",
                    agence="Castries",
                    est_admin=True,
                    doit_changer_mot_de_passe=False,
                    poles=[ComptePole(pole="Administration")],
                )
            )
            db.commit()
    finally:
        db.close()

    print()
    print("============================================")
    print(" Compte de test (administrateur)")
    print("============================================")
    print(" Cree a l'instant." if cree else " Deja existant (mot de passe inchange depuis sa creation).")
    print(f" Identifiant  : {IDENTIFIANT}")
    print(f" Mot de passe : {MOT_DE_PASSE}")
    print("============================================")
    print()


if __name__ == "__main__":
    main()
