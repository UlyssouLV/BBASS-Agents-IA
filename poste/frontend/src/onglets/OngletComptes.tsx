import { useState, type Dispatch, type FormEvent, type SetStateAction } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  useComptesQuery,
  useCreerCompteMutation,
  useDeconnexionForceeMutation,
  useModifierCompteMutation,
  useModifierStatutAdminMutation,
  useReinitialiserMotDePasseMutation,
  useSupprimerCompteMutation,
  type CompteAdmin,
} from "@/hooks/useComptes";
import { ErreurApi } from "@/lib/api";

// Mêmes six pôles que CONTEXT.md et l'ancien fieldset d'app.js
// (#modification-poles / #creation-poles).
const POLES = ["Administration", "Appels d'offres", "Foncier", "DAO", "Urbanisme", "Détection de réseaux"];

type Action =
  | { type: "creation" }
  | { type: "modification"; compte: CompteAdmin }
  | { type: "statut-admin"; compte: CompteAdmin }
  | { type: "suppression"; compte: CompteAdmin }
  | null;

function messageErreur(erreur: unknown, messageParDefaut: string): string | null {
  if (!erreur) {
    return null;
  }
  return erreur instanceof ErreurApi ? erreur.message : messageParDefaut;
}

// Réécriture React de la section #onglet-comptes d'app.js : le tableau des
// comptes reste affiché par défaut, chaque action (création, modification,
// changement de statut administrateur, suppression) s'ouvre désormais dans
// une Dialog dédiée au lieu de blocs empilés en permanence ; réinitialisation
// du mot de passe et déconnexion forcée restent des actions directes, dont
// le résultat est révélé en toast plutôt que dans un bloc qui reste affiché
// (voir docs/specs/v1.2.0-interface-poste.md et issue #65). Aucun
// changement de comportement ni de sécurité : mêmes endpoints, même
// exigence de Clé d'administration VM pour suppression et changement de
// statut administrateur.
export function OngletComptes() {
  const [action, setAction] = useState<Action>(null);

  const comptesQuery = useComptesQuery();
  const reinitialiserMotDePasseMutation = useReinitialiserMotDePasseMutation();
  const deconnexionForceeMutation = useDeconnexionForceeMutation();

  function fermerDialog() {
    setAction(null);
  }

  function reinitialiserMotDePasse(compte: CompteAdmin) {
    reinitialiserMotDePasseMutation.mutate(compte.identifiant, {
      onSuccess: (donnees) => {
        toast.success(`Mot de passe réinitialisé pour ${compte.identifiant}`, {
          description: `Nouveau mot de passe à transmettre au collaborateur : ${donnees.mot_de_passe}`,
        });
      },
      onError: (erreur) => {
        toast.error(erreur instanceof ErreurApi ? erreur.message : "La réinitialisation du mot de passe a échoué. Réessayez plus tard.");
      },
    });
  }

  function forcerLaDeconnexion(compte: CompteAdmin) {
    deconnexionForceeMutation.mutate(compte.identifiant, {
      onSuccess: () => {
        toast.success(`Déconnexion forcée pour ${compte.identifiant}.`);
      },
      onError: (erreur) => {
        toast.error(erreur instanceof ErreurApi ? erreur.message : "La déconnexion forcée a échoué. Réessayez plus tard.");
      },
    });
  }

  const erreurComptes = messageErreur(comptesQuery.error, "Le chargement des comptes a échoué. Réessayez plus tard.");

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-sm font-semibold">Comptes</h2>
        <Button type="button" size="sm" onClick={() => setAction({ type: "creation" })}>
          Créer un compte
        </Button>
      </div>

      {comptesQuery.isLoading && <output>Chargement…</output>}
      {erreurComptes && (
        <p role="alert" className="mb-2 text-sm text-destructive">
          {erreurComptes}
        </p>
      )}

      {comptesQuery.data && (
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border text-left">
              <th className="py-1.5 pr-4 font-medium">Identifiant</th>
              <th className="py-1.5 pr-4 font-medium">Prénom</th>
              <th className="py-1.5 pr-4 font-medium">Nom</th>
              <th className="py-1.5 pr-4 font-medium">Agence</th>
              <th className="py-1.5 pr-4 font-medium">Pôles</th>
              <th className="py-1.5 pr-4 font-medium">Email</th>
              <th className="py-1.5 font-medium">
                <span className="sr-only">Actions</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {comptesQuery.data.map((compte) => (
              <tr key={compte.identifiant} className="border-b border-border last:border-0">
                <td className="py-1.5 pr-4">{compte.identifiant}</td>
                <td className="py-1.5 pr-4">{compte.prenom}</td>
                <td className="py-1.5 pr-4">{compte.nom}</td>
                <td className="py-1.5 pr-4">{compte.agence}</td>
                <td className="py-1.5 pr-4">{compte.poles.join(", ")}</td>
                <td className="py-1.5 pr-4">{compte.email ?? ""}</td>
                <td className="py-1.5">
                  <div className="flex flex-wrap gap-x-3 gap-y-1 text-xs">
                    <button
                      type="button"
                      className="hover:underline"
                      onClick={() => setAction({ type: "modification", compte })}
                    >
                      Modifier
                    </button>
                    <button
                      type="button"
                      className="hover:underline disabled:pointer-events-none disabled:opacity-50"
                      disabled={reinitialiserMotDePasseMutation.isPending}
                      onClick={() => reinitialiserMotDePasse(compte)}
                    >
                      Réinitialiser le mot de passe
                    </button>
                    <button
                      type="button"
                      className="hover:underline disabled:pointer-events-none disabled:opacity-50"
                      disabled={deconnexionForceeMutation.isPending}
                      onClick={() => forcerLaDeconnexion(compte)}
                    >
                      Forcer la déconnexion
                    </button>
                    <button
                      type="button"
                      className="hover:underline"
                      onClick={() => setAction({ type: "statut-admin", compte })}
                    >
                      {compte.est_admin ? "Rétrograder" : "Promouvoir administrateur"}
                    </button>
                    <button
                      type="button"
                      className="text-destructive hover:underline"
                      onClick={() => setAction({ type: "suppression", compte })}
                    >
                      Supprimer
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <Dialog open={action !== null} onOpenChange={(ouvert) => !ouvert && fermerDialog()}>
        <DialogContent>
          {action?.type === "creation" && (
            <FormulaireCreationCompte
              onFermer={fermerDialog}
              onCree={(compte) => {
                fermerDialog();
                toast.success(`Compte ${compte.identifiant} créé.`, {
                  description: `Mot de passe généré à transmettre au collaborateur : ${compte.mot_de_passe}`,
                });
              }}
            />
          )}
          {action?.type === "modification" && (
            <FormulaireModificationCompte compte={action.compte} onFermer={fermerDialog} onModifie={fermerDialog} />
          )}
          {action?.type === "statut-admin" && (
            <FormulaireStatutAdmin
              compte={action.compte}
              onFermer={fermerDialog}
              onConfirme={(compte) => {
                fermerDialog();
                toast.success(
                  `${compte.identifiant} est désormais ${compte.est_admin ? "administrateur" : "non-administrateur"}.`
                );
              }}
            />
          )}
          {action?.type === "suppression" && (
            <FormulaireSuppressionCompte
              compte={action.compte}
              onFermer={fermerDialog}
              onSupprime={(identifiant) => {
                fermerDialog();
                toast.success(`Compte ${identifiant} supprimé définitivement.`);
              }}
            />
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}

interface ChampsIdentiteProps {
  prenom: string;
  setPrenom: (valeur: string) => void;
  nom: string;
  setNom: (valeur: string) => void;
  email: string;
  setEmail: (valeur: string) => void;
  agence: string;
  setAgence: (valeur: string) => void;
  poles: string[];
  setPoles: Dispatch<SetStateAction<string[]>>;
}

// Champs communs à la création et à la modification (voir
// CompteCreationRequest / CompteModificationRequest côté poste.schemas).
function ChampsIdentite({
  prenom,
  setPrenom,
  nom,
  setNom,
  email,
  setEmail,
  agence,
  setAgence,
  poles,
  setPoles,
}: Readonly<ChampsIdentiteProps>) {
  function basculerPole(pole: string, coche: boolean) {
    setPoles((actuels) => (coche ? [...actuels, pole] : actuels.filter((valeur) => valeur !== pole)));
  }

  return (
    <>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="prenom">Prénom</Label>
        <Input id="prenom" required value={prenom} onChange={(evenement) => setPrenom(evenement.target.value)} />
      </div>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="nom">Nom</Label>
        <Input id="nom" required value={nom} onChange={(evenement) => setNom(evenement.target.value)} />
      </div>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="email">Email (optionnel)</Label>
        <Input
          id="email"
          type="email"
          value={email}
          onChange={(evenement) => setEmail(evenement.target.value)}
        />
      </div>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="agence">Agence</Label>
        <Input id="agence" required value={agence} onChange={(evenement) => setAgence(evenement.target.value)} />
      </div>
      <fieldset className="flex flex-col gap-1.5">
        <legend className="text-sm font-medium">Pôles</legend>
        <div className="flex flex-col gap-1.5">
          {POLES.map((pole) => (
            <label key={pole} className="flex items-center gap-2 text-sm font-normal">
              <Checkbox
                checked={poles.includes(pole)}
                onCheckedChange={(coche) => basculerPole(pole, coche === true)}
              />
              {pole}
            </label>
          ))}
        </div>
      </fieldset>
    </>
  );
}

interface FormulaireCreationCompteProps {
  onFermer: () => void;
  onCree: (compte: { identifiant: string; mot_de_passe: string }) => void;
}

function FormulaireCreationCompte({ onFermer, onCree }: Readonly<FormulaireCreationCompteProps>) {
  const mutation = useCreerCompteMutation();
  const [identifiant, setIdentifiant] = useState("");
  const [prenom, setPrenom] = useState("");
  const [nom, setNom] = useState("");
  const [email, setEmail] = useState("");
  const [agence, setAgence] = useState("");
  const [poles, setPoles] = useState<string[]>([]);
  const [erreurLocale, setErreurLocale] = useState<string | null>(null);

  function gererEnvoi(evenement: FormEvent<HTMLFormElement>) {
    evenement.preventDefault();
    setErreurLocale(null);

    if (poles.length === 0) {
      setErreurLocale("Sélectionnez au moins un pôle.");
      return;
    }

    mutation.mutate(
      { identifiant, prenom, nom, email: email || null, agence, poles },
      { onSuccess: onCree }
    );
  }

  const messageErr = erreurLocale ?? messageErreur(mutation.error, "La création du compte a échoué. Réessayez plus tard.");

  return (
    <>
      <DialogHeader>
        <DialogTitle>Créer un compte</DialogTitle>
      </DialogHeader>
      <form onSubmit={gererEnvoi} className="flex flex-col gap-4">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="identifiant">Identifiant</Label>
          <Input
            id="identifiant"
            autoComplete="off"
            required
            value={identifiant}
            onChange={(evenement) => setIdentifiant(evenement.target.value)}
          />
        </div>
        <ChampsIdentite
          prenom={prenom}
          setPrenom={setPrenom}
          nom={nom}
          setNom={setNom}
          email={email}
          setEmail={setEmail}
          agence={agence}
          setAgence={setAgence}
          poles={poles}
          setPoles={setPoles}
        />
        {messageErr && (
          <p role="alert" className="text-sm text-destructive">
            {messageErr}
          </p>
        )}
        <DialogFooter>
          <Button type="button" variant="outline" onClick={onFermer}>
            Annuler
          </Button>
          <Button type="submit" disabled={mutation.isPending}>
            Créer le compte
          </Button>
        </DialogFooter>
      </form>
    </>
  );
}

interface FormulaireModificationCompteProps {
  compte: CompteAdmin;
  onFermer: () => void;
  onModifie: (compte: CompteAdmin) => void;
}

function FormulaireModificationCompte({
  compte,
  onFermer,
  onModifie,
}: Readonly<FormulaireModificationCompteProps>) {
  const mutation = useModifierCompteMutation();
  const [prenom, setPrenom] = useState(compte.prenom);
  const [nom, setNom] = useState(compte.nom);
  const [email, setEmail] = useState(compte.email ?? "");
  const [agence, setAgence] = useState(compte.agence);
  const [poles, setPoles] = useState<string[]>(compte.poles);
  const [erreurLocale, setErreurLocale] = useState<string | null>(null);

  function gererEnvoi(evenement: FormEvent<HTMLFormElement>) {
    evenement.preventDefault();
    setErreurLocale(null);

    if (poles.length === 0) {
      setErreurLocale("Sélectionnez au moins un pôle.");
      return;
    }

    mutation.mutate(
      { identifiant: compte.identifiant, prenom, nom, email: email || null, agence, poles },
      { onSuccess: onModifie }
    );
  }

  const messageErr =
    erreurLocale ?? messageErreur(mutation.error, "La modification du compte a échoué. Réessayez plus tard.");

  return (
    <>
      <DialogHeader>
        <DialogTitle>Modifier le compte {compte.identifiant}</DialogTitle>
      </DialogHeader>
      <form onSubmit={gererEnvoi} className="flex flex-col gap-4">
        <ChampsIdentite
          prenom={prenom}
          setPrenom={setPrenom}
          nom={nom}
          setNom={setNom}
          email={email}
          setEmail={setEmail}
          agence={agence}
          setAgence={setAgence}
          poles={poles}
          setPoles={setPoles}
        />
        {messageErr && (
          <p role="alert" className="text-sm text-destructive">
            {messageErr}
          </p>
        )}
        <DialogFooter>
          <Button type="button" variant="outline" onClick={onFermer}>
            Annuler
          </Button>
          <Button type="submit" disabled={mutation.isPending}>
            Enregistrer
          </Button>
        </DialogFooter>
      </form>
    </>
  );
}

interface FormulaireStatutAdminProps {
  compte: CompteAdmin;
  onFermer: () => void;
  onConfirme: (compte: CompteAdmin) => void;
}

function FormulaireStatutAdmin({ compte, onFermer, onConfirme }: Readonly<FormulaireStatutAdminProps>) {
  const mutation = useModifierStatutAdminMutation();
  const [cleAdminVm, setCleAdminVm] = useState("");
  const nouveauStatut = !compte.est_admin;
  const action = nouveauStatut ? "Promouvoir" : "Rétrograder";

  function gererEnvoi(evenement: FormEvent<HTMLFormElement>) {
    evenement.preventDefault();
    mutation.mutate(
      { identifiant: compte.identifiant, estAdmin: nouveauStatut, cleAdminVm },
      { onSuccess: onConfirme }
    );
  }

  const messageErr = messageErreur(mutation.error, "Le changement de statut administrateur a échoué. Réessayez plus tard.");

  return (
    <>
      <DialogHeader>
        <DialogTitle>
          {action} le compte {compte.identifiant}
        </DialogTitle>
        <DialogDescription>La Clé d'administration VM est requise pour confirmer ce changement.</DialogDescription>
      </DialogHeader>
      <form onSubmit={gererEnvoi} className="flex flex-col gap-4">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="statut-admin-cle">Clé d'administration VM</Label>
          <Input
            id="statut-admin-cle"
            type="password"
            required
            value={cleAdminVm}
            onChange={(evenement) => setCleAdminVm(evenement.target.value)}
          />
        </div>
        {messageErr && (
          <p role="alert" className="text-sm text-destructive">
            {messageErr}
          </p>
        )}
        <DialogFooter>
          <Button type="button" variant="outline" onClick={onFermer}>
            Annuler
          </Button>
          <Button type="submit" disabled={mutation.isPending}>
            Confirmer
          </Button>
        </DialogFooter>
      </form>
    </>
  );
}

interface FormulaireSuppressionCompteProps {
  compte: CompteAdmin;
  onFermer: () => void;
  onSupprime: (identifiant: string) => void;
}

function FormulaireSuppressionCompte({
  compte,
  onFermer,
  onSupprime,
}: Readonly<FormulaireSuppressionCompteProps>) {
  const mutation = useSupprimerCompteMutation();
  const [cleAdminVm, setCleAdminVm] = useState("");

  function gererEnvoi(evenement: FormEvent<HTMLFormElement>) {
    evenement.preventDefault();
    mutation.mutate(
      { identifiant: compte.identifiant, cleAdminVm },
      { onSuccess: () => onSupprime(compte.identifiant) }
    );
  }

  const messageErr = messageErreur(mutation.error, "La suppression du compte a échoué. Réessayez plus tard.");

  return (
    <>
      <DialogHeader>
        <DialogTitle>Supprimer le compte {compte.identifiant}</DialogTitle>
        <DialogDescription>
          Cette action est définitive. La Clé d'administration VM est requise pour confirmer la suppression.
        </DialogDescription>
      </DialogHeader>
      <form onSubmit={gererEnvoi} className="flex flex-col gap-4">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="suppression-cle">Clé d'administration VM</Label>
          <Input
            id="suppression-cle"
            type="password"
            required
            value={cleAdminVm}
            onChange={(evenement) => setCleAdminVm(evenement.target.value)}
          />
        </div>
        {messageErr && (
          <p role="alert" className="text-sm text-destructive">
            {messageErr}
          </p>
        )}
        <DialogFooter>
          <Button type="button" variant="outline" onClick={onFermer}>
            Annuler
          </Button>
          <Button type="submit" variant="destructive" disabled={mutation.isPending}>
            Confirmer la suppression
          </Button>
        </DialogFooter>
      </form>
    </>
  );
}
