import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";

interface PuceCompteProps {
  compte: {
    prenom: string;
    nom: string;
    poles: string[];
    agence: string;
    est_admin: boolean;
  };
  onOuvrirProfil: () => void;
  onOuvrirPanelAdministration: () => void;
}

// Bas de la barre latérale : identité du compte, Profil, et le panel
// pour un compte administrateur.
export function PuceCompte({
  compte,
  onOuvrirProfil,
  onOuvrirPanelAdministration,
}: Readonly<PuceCompteProps>) {
  const poleAgence = [compte.poles.join(", "), compte.agence].filter(Boolean).join(" — ");
  const initiales = `${compte.prenom.charAt(0)}${compte.nom.charAt(0)}`.toUpperCase();

  return (
    <div className="flex flex-col gap-2 border-t border-border p-4">
      <div className="flex items-center gap-2">
        <Avatar>
          <AvatarFallback>{initiales}</AvatarFallback>
        </Avatar>
        <div className="min-w-0">
          <p className="truncate text-sm font-medium">
            {compte.prenom} {compte.nom}
          </p>
          <p className="truncate text-xs text-muted-foreground">{poleAgence}</p>
        </div>
      </div>
      <Button type="button" variant="outline" size="sm" onClick={onOuvrirProfil}>
        Profil
      </Button>
      {compte.est_admin && (
        <Button type="button" variant="outline" size="sm" onClick={onOuvrirPanelAdministration}>
          Panel d'administration
        </Button>
      )}
    </div>
  );
}
