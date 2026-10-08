import { Badge } from "@/components/ui/badge";
import { TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

export interface CompteLigneAdmin {
  identifiant: string;
  prenom: string;
  nom: string;
  agence: string;
  poles: string[];
  est_admin: boolean;
  email: string | null;
}

interface ActionsCompteProps {
  compte: CompteLigneAdmin;
  reinitialisationEnCours: boolean;
  deconnexionEnCours: boolean;
  onModifier: () => void;
  onReinitialiser: () => void;
  onForcerDeconnexion: () => void;
  onChangerStatut: () => void;
  onSupprimer: () => void;
}

export function EnteteComptesAdmin() {
  return (
    <TableHeader>
      <TableRow>
        <TableHead>Identifiant</TableHead>
        <TableHead>Prénom</TableHead>
        <TableHead>Nom</TableHead>
        <TableHead>Agence</TableHead>
        <TableHead>Pôles</TableHead>
        <TableHead>Statut</TableHead>
        <TableHead>Email</TableHead>
        <TableHead>
          <span className="sr-only">Actions</span>
        </TableHead>
      </TableRow>
    </TableHeader>
  );
}

export function LigneCompteAdmin({
  compte,
  reinitialisationEnCours,
  deconnexionEnCours,
  onModifier,
  onReinitialiser,
  onForcerDeconnexion,
  onChangerStatut,
  onSupprimer,
}: Readonly<ActionsCompteProps>) {
  return (
    <TableRow>
      <TableCell>{compte.identifiant}</TableCell>
      <TableCell>{compte.prenom}</TableCell>
      <TableCell>{compte.nom}</TableCell>
      <TableCell>{compte.agence}</TableCell>
      <TableCell>
        <div className="flex flex-wrap gap-1">
          {compte.poles.map((pole) => (
            <Badge key={pole} variant="outline">
              {pole}
            </Badge>
          ))}
        </div>
      </TableCell>
      <TableCell>
        <Badge variant={compte.est_admin ? "default" : "secondary"}>
          {compte.est_admin ? "Administrateur" : "Standard"}
        </Badge>
      </TableCell>
      <TableCell>{compte.email ?? ""}</TableCell>
      <TableCell>
        <div className="flex flex-wrap gap-x-3 gap-y-1 text-xs">
          <button type="button" className="hover:underline" onClick={onModifier}>
            Modifier
          </button>
          <button
            type="button"
            className="hover:underline disabled:pointer-events-none disabled:opacity-50"
            disabled={reinitialisationEnCours}
            onClick={onReinitialiser}
          >
            Réinitialiser le mot de passe
          </button>
          <button
            type="button"
            className="hover:underline disabled:pointer-events-none disabled:opacity-50"
            disabled={deconnexionEnCours}
            onClick={onForcerDeconnexion}
          >
            Forcer la déconnexion
          </button>
          <button type="button" className="hover:underline" onClick={onChangerStatut}>
            {compte.est_admin ? "Rétrograder" : "Promouvoir administrateur"}
          </button>
          <button type="button" className="text-destructive hover:underline" onClick={onSupprimer}>
            Supprimer
          </button>
        </div>
      </TableCell>
    </TableRow>
  );
}
