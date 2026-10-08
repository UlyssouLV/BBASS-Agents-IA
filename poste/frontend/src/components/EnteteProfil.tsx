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
      <Button variant="outline" onClick={onDeconnexion} disabled={deconnexionEnCours}>
        Se déconnecter
      </Button>
    </header>
  );
}
