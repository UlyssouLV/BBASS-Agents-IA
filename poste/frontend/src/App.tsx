import { Toaster } from "@/components/ui/sonner";
import { useSession } from "@/hooks/useSession";
import { EcranChangementMotDePasse } from "@/screens/EcranChangementMotDePasse";
import { EcranCompte } from "@/screens/EcranCompte";
import { EcranConnexion } from "@/screens/EcranConnexion";

export function App() {
  const { compte, chargementInitial, connexion, changerMotDePasse, deconnexion } = useSession();

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
