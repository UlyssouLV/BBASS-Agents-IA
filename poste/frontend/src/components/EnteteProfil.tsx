import { MenuConfiguration } from "@/components/MenuConfiguration";
import { Button } from "@/components/ui/button";

interface EnteteProfilProps {
  onRetour: () => void;
  onDeconnexion: () => void;
  deconnexionEnCours: boolean;
}

export function EnteteProfil({ onRetour, onDeconnexion, deconnexionEnCours }: Readonly<EnteteProfilProps>) {
  return (
    <header className="mb-4 flex items-center justify-between gap-4">
      <Button variant="outline" onClick={onRetour}>
        ← Retour au chat
      </Button>
      <h1 className="text-lg font-semibold">Profil</h1>
      <div className="flex items-center gap-2">
        <Button variant="outline" onClick={onDeconnexion} disabled={deconnexionEnCours}>
          Se déconnecter
        </Button>
        {/* Menu « … » (spec 1.6.2, point 9), le même qu'à l'écran de connexion. */}
        <MenuConfiguration />
      </div>
    </header>
  );
}
