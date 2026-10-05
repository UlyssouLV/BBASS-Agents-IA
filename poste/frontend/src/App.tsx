import { useEffect } from "react";

import { Button } from "@/components/ui/button";
import { Toaster } from "@/components/ui/sonner";
import { useSession } from "@/hooks/useSession";
import { EcranChangementMotDePasse } from "@/screens/EcranChangementMotDePasse";
import { EcranCompte } from "@/screens/EcranCompte";
import { EcranConnexion } from "@/screens/EcranConnexion";

// Mode développeur (spec 1.3.0) : raccourci discret, actif quel que soit
// l'écran affiché (connexion comprise), qui ouvre l'inspecteur des échanges
// avec le modèle dans un nouvel onglet — le chat en cours reste inchangé.
function useRaccourciInspecteur() {
  useEffect(() => {
    function gererTouche(evenement: KeyboardEvent) {
      if (evenement.ctrlKey && evenement.shiftKey && !evenement.altKey && evenement.key.toLowerCase() === "d") {
        evenement.preventDefault();
        window.open("/inspecteur", "_blank", "noopener");
      }
    }
    globalThis.addEventListener("keydown", gererTouche);
    return () => globalThis.removeEventListener("keydown", gererTouche);
  }, []);
}

export function App() {
  const { compte, chargementInitial, erreurInitiale, reessayerChargementInitial, connexion, changerMotDePasse, deconnexion } =
    useSession();
  useRaccourciInspecteur();

  return (
    <>
      {_ecran()}
      <Toaster />
    </>
  );

  // Le temps de savoir si une session existe déjà (restauration via
  // /compte), on n'affiche rien plutôt que de montrer l'écran de connexion
  // puis de basculer aussitôt sur l'écran compte.
  function _ecran() {
    if (chargementInitial) {
      return null;
    }

    // Un 401 sur /compte vide déjà le cache (chargerCompteConnecte, voir
    // useSession.ts) : compte === null y arrive normalement. Une erreur ici
    // veut dire que /compte n'a pas pu être contacté du tout — ne pas le
    // confondre avec un compte déconnecté sous peine de masquer une panne
    // réseau/serveur derrière un simple écran de connexion.
    if (!compte && erreurInitiale) {
      return (
        <main className="mx-auto mt-24 w-full max-w-sm text-center">
          <p role="alert" className="mb-4 text-sm text-destructive">
            Impossible de vérifier la session en cours. Vérifiez la connexion au serveur puis réessayez.
          </p>
          <Button onClick={() => reessayerChargementInitial()}>Réessayer</Button>
        </main>
      );
    }

    if (!compte) {
      return <EcranConnexion connexion={connexion} />;
    }

    // Un compte qui doit encore changer son mot de passe (création ou
    // réinitialisation par un administrateur) ne doit jamais atteindre
    // l'écran compte, ni à la connexion ni à la restauration de session.
    if (compte.doit_changer_mot_de_passe) {
      return <EcranChangementMotDePasse changerMotDePasse={changerMotDePasse} />;
    }

    return <EcranCompte compte={compte} deconnexion={deconnexion} />;
  }
}
