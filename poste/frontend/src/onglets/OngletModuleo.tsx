import { useState, type FormEvent } from "react";
import { toast } from "sonner";

import { ArbreDroitsModuleo, type DroitsCoches } from "@/components/ArbreDroitsModuleo";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useComptesQuery } from "@/hooks/useComptes";
import {
  useCatalogueModuleoQuery,
  useCreerGroupeModuleoMutation,
  useDroitsGroupeModuleoQuery,
  useGroupesModuleoQuery,
  useJournalModuleoQuery,
  useModifierRattachementModuleoMutation,
  useRattachementsModuleoQuery,
  useRemplacerDroitsGroupeModuleoMutation,
  useRenommerGroupeModuleoMutation,
  useSupprimerGroupeModuleoMutation,
  type ApplicationModuleo,
  type GroupeModuleo,
  type ModificationRattachementVariables,
} from "@/hooks/useModuleo";
import { messageErreur } from "@/lib/api";

const APPLICATIONS: { application: ApplicationModuleo; libelle: string }[] = [
  { application: "cogeo", libelle: "Cogeo" },
  { application: "planning", libelle: "Planning" },
];

const CLASSE_SELECT = "h-8 rounded-md border border-input bg-transparent px-2 text-sm";

type Action =
  | { type: "creation" }
  | { type: "renommage"; groupe: GroupeModuleo }
  | { type: "droits"; groupe: GroupeModuleo }
  | { type: "suppression"; groupe: GroupeModuleo }
  | null;

function Erreur({ erreur, parDefaut }: Readonly<{ erreur: unknown; parDefaut: string }>) {
  const message = messageErreur(erreur, parDefaut);
  return message ? (
    <p role="alert" className="mb-2 text-sm text-destructive">
      {message}
    </p>
  ) : null;
}

function toastErreur(erreur: unknown, parDefaut: string) {
  toast.error(messageErreur(erreur, parDefaut) ?? parDefaut);
}

// Sous-onglet Outils → Moduléo (spec 1.5.3, #213) : groupes Cogeo /
// Planning et leurs droits, rattachements des comptes, journal minimal.
// Le catalogue des cases reste en lecture seule (ADR-0019) : aucune UI pour
// en ajouter ou en supprimer une.
export function OngletModuleo() {
  return (
    <div className="space-y-8">
      <SectionGroupes />
      <SectionRattachements />
      <SectionJournal />
    </div>
  );
}

function SectionGroupes() {
  const [action, setAction] = useState<Action>(null);
  const groupesQuery = useGroupesModuleoQuery();

  function fermer() {
    setAction(null);
  }

  return (
    <section>
      <div className="mb-2 flex items-center justify-between">
        <h2 className="text-sm font-semibold">Groupes Moduléo</h2>
        <Button type="button" size="sm" onClick={() => setAction({ type: "creation" })}>
          Créer un groupe
        </Button>
      </div>
      {groupesQuery.isLoading && <output>Chargement…</output>}
      <Erreur erreur={groupesQuery.error} parDefaut="Le chargement des groupes Moduléo a échoué." />
      {groupesQuery.data && (
        <div className="grid gap-4 sm:grid-cols-2">
          {APPLICATIONS.map(({ application, libelle }) => (
            <div key={application}>
              <h3 className="mb-1 text-sm text-muted-foreground">{libelle}</h3>
              <ul className="space-y-1">
                {groupesQuery.data
                  .filter((groupe) => groupe.application === application)
                  .map((groupe) => (
                    <li key={groupe.id} className="flex items-center justify-between gap-2 rounded-md border px-2 py-1">
                      <span className="text-sm">{groupe.nom}</span>
                      <span className="flex gap-1">
                        <Button type="button" size="sm" variant="outline" onClick={() => setAction({ type: "droits", groupe })}>
                          Droits
                        </Button>
                        <Button type="button" size="sm" variant="outline" onClick={() => setAction({ type: "renommage", groupe })}>
                          Renommer
                        </Button>
                        <Button type="button" size="sm" variant="outline" onClick={() => setAction({ type: "suppression", groupe })}>
                          Supprimer
                        </Button>
                      </span>
                    </li>
                  ))}
              </ul>
            </div>
          ))}
        </div>
      )}

      <Dialog open={action !== null} onOpenChange={(ouvert) => !ouvert && fermer()}>
        <DialogContent className={action?.type === "droits" ? "max-h-[85vh] overflow-y-auto sm:max-w-2xl" : undefined}>
          {action?.type === "creation" && <FormulaireCreationGroupe onFermer={fermer} />}
          {action?.type === "renommage" && <FormulaireRenommageGroupe groupe={action.groupe} onFermer={fermer} />}
          {action?.type === "droits" && <FormulaireDroitsGroupe groupe={action.groupe} onFermer={fermer} />}
          {action?.type === "suppression" && <FormulaireSuppressionGroupe groupe={action.groupe} onFermer={fermer} />}
        </DialogContent>
      </Dialog>
    </section>
  );
}

function FormulaireCreationGroupe({ onFermer }: Readonly<{ onFermer: () => void }>) {
  const [application, setApplication] = useState<ApplicationModuleo>("cogeo");
  const [nom, setNom] = useState("");
  const creerMutation = useCreerGroupeModuleoMutation();

  function soumettre(e: FormEvent) {
    e.preventDefault();
    creerMutation.mutate(
      { application, nom: nom.trim() },
      {
        onSuccess: (groupe) => {
          toast.success(`Groupe ${groupe.nom} créé.`);
          onFermer();
        },
      }
    );
  }

  return (
    <form onSubmit={soumettre} className="space-y-3">
      <DialogHeader>
        <DialogTitle>Créer un groupe Moduléo</DialogTitle>
        <DialogDescription>Le groupe naît sans aucun droit : cochez-les ensuite.</DialogDescription>
      </DialogHeader>
      <div className="space-y-1">
        <Label htmlFor="groupe-application">Application</Label>
        <select
          id="groupe-application"
          className={CLASSE_SELECT}
          value={application}
          onChange={(e) => setApplication(e.target.value as ApplicationModuleo)}
        >
          {APPLICATIONS.map(({ application: valeur, libelle }) => (
            <option key={valeur} value={valeur}>
              {libelle}
            </option>
          ))}
        </select>
      </div>
      <div className="space-y-1">
        <Label htmlFor="groupe-nom">Nom</Label>
        <Input id="groupe-nom" value={nom} onChange={(e) => setNom(e.target.value)} required />
      </div>
      <Erreur erreur={creerMutation.error} parDefaut="La création du groupe a échoué." />
      <DialogFooter>
        <Button type="button" variant="outline" onClick={onFermer}>
          Annuler
        </Button>
        <Button type="submit" disabled={creerMutation.isPending || !nom.trim()}>
          Créer
        </Button>
      </DialogFooter>
    </form>
  );
}

function FormulaireRenommageGroupe({ groupe, onFermer }: Readonly<{ groupe: GroupeModuleo; onFermer: () => void }>) {
  const [nom, setNom] = useState(groupe.nom);
  const renommerMutation = useRenommerGroupeModuleoMutation();

  function soumettre(e: FormEvent) {
    e.preventDefault();
    renommerMutation.mutate(
      { id: groupe.id, nom: nom.trim() },
      {
        onSuccess: () => {
          toast.success(`Groupe renommé en ${nom.trim()}.`);
          onFermer();
        },
      }
    );
  }

  return (
    <form onSubmit={soumettre} className="space-y-3">
      <DialogHeader>
        <DialogTitle>Renommer le groupe {groupe.nom}</DialogTitle>
      </DialogHeader>
      <div className="space-y-1">
        <Label htmlFor="renommage-nom">Nouveau nom</Label>
        <Input id="renommage-nom" value={nom} onChange={(e) => setNom(e.target.value)} required />
      </div>
      <Erreur erreur={renommerMutation.error} parDefaut="Le renommage du groupe a échoué." />
      <DialogFooter>
        <Button type="button" variant="outline" onClick={onFermer}>
          Annuler
        </Button>
        <Button type="submit" disabled={renommerMutation.isPending || !nom.trim()}>
          Renommer
        </Button>
      </DialogFooter>
    </form>
  );
}

function FormulaireSuppressionGroupe({ groupe, onFermer }: Readonly<{ groupe: GroupeModuleo; onFermer: () => void }>) {
  const supprimerMutation = useSupprimerGroupeModuleoMutation();

  return (
    <div className="space-y-3">
      <DialogHeader>
        <DialogTitle>Supprimer le groupe {groupe.nom} ?</DialogTitle>
        <DialogDescription>Refusé tant qu'un compte y est rattaché : rattachez-le d'abord ailleurs.</DialogDescription>
      </DialogHeader>
      {/* Refus visible (spec 1.5.3, user story 7) : le texte de la VM nomme les comptes rattachés. */}
      <Erreur erreur={supprimerMutation.error} parDefaut="La suppression du groupe a échoué." />
      <DialogFooter>
        <Button type="button" variant="outline" onClick={onFermer}>
          Annuler
        </Button>
        <Button
          type="button"
          variant="destructive"
          disabled={supprimerMutation.isPending}
          onClick={() =>
            supprimerMutation.mutate(groupe.id, {
              onSuccess: () => {
                toast.success(`Groupe ${groupe.nom} supprimé.`);
                onFermer();
              },
            })
          }
        >
          Supprimer
        </Button>
      </DialogFooter>
    </div>
  );
}

function FormulaireDroitsGroupe({ groupe, onFermer }: Readonly<{ groupe: GroupeModuleo; onFermer: () => void }>) {
  const catalogueQuery = useCatalogueModuleoQuery();
  const droitsQuery = useDroitsGroupeModuleoQuery(groupe.id);

  return (
    <div className="space-y-3">
      <DialogHeader>
        <DialogTitle>Droits du groupe {groupe.nom}</DialogTitle>
        <DialogDescription>
          Cochez les cases comme dans Moduléo. Une case manquante relève d'une évolution du catalogue (intervention dév).
        </DialogDescription>
      </DialogHeader>
      {(catalogueQuery.isLoading || droitsQuery.isLoading) && <output>Chargement…</output>}
      <Erreur erreur={catalogueQuery.error} parDefaut="Le chargement du catalogue a échoué." />
      <Erreur erreur={droitsQuery.error} parDefaut="Le chargement des droits du groupe a échoué." />
      {catalogueQuery.data && droitsQuery.data && (
        <EditeurDroits
          groupe={groupe}
          categories={catalogueQuery.data[groupe.application]}
          initiaux={new Map(droitsQuery.data.map((droit) => [droit.chemin, droit.conditions]))}
          onFermer={onFermer}
        />
      )}
    </div>
  );
}

function EditeurDroits({
  groupe,
  categories,
  initiaux,
  onFermer,
}: Readonly<{
  groupe: GroupeModuleo;
  categories: Parameters<typeof ArbreDroitsModuleo>[0]["categories"];
  initiaux: DroitsCoches;
  onFermer: () => void;
}>) {
  const [coches, setCoches] = useState<DroitsCoches>(initiaux);
  const remplacerMutation = useRemplacerDroitsGroupeModuleoMutation();

  function enregistrer() {
    remplacerMutation.mutate(
      { id: groupe.id, droits: [...coches].map(([chemin, conditions]) => ({ chemin, conditions })) },
      {
        onSuccess: () => {
          toast.success(`Droits du groupe ${groupe.nom} enregistrés.`);
          onFermer();
        },
      }
    );
  }

  return (
    <>
      <ArbreDroitsModuleo categories={categories} coches={coches} onChange={setCoches} />
      <Erreur erreur={remplacerMutation.error} parDefaut="L'enregistrement des droits a échoué." />
      <DialogFooter>
        <Button type="button" variant="outline" onClick={onFermer}>
          Annuler
        </Button>
        <Button type="button" disabled={remplacerMutation.isPending} onClick={enregistrer}>
          Enregistrer
        </Button>
      </DialogFooter>
    </>
  );
}

function SectionRattachements() {
  const rattachementsQuery = useRattachementsModuleoQuery();
  const groupesQuery = useGroupesModuleoQuery();
  const comptesQuery = useComptesQuery();
  const modifierMutation = useModifierRattachementModuleoMutation();
  const [noms, setNoms] = useState<Record<string, string>>({});

  const comptes = new Map((comptesQuery.data ?? []).map((compte) => [compte.identifiant, compte]));
  const groupes = groupesQuery.data ?? [];

  function modifier(variables: ModificationRattachementVariables, succes: string) {
    modifierMutation.mutate(variables, {
      onSuccess: () => {
        toast.success(succes);
        setNoms((actuels) => ({ ...actuels, [variables.identifiant]: "" }));
      },
      onError: (erreur) => toastErreur(erreur, "La modification du rattachement a échoué. Réessayez plus tard."),
    });
  }

  function choixGroupe(identifiant: string, application: ApplicationModuleo, valeur: number | null) {
    const champ = application === "cogeo" ? "groupe_cogeo_id" : "groupe_planning_id";
    return (
      <select
        aria-label={`Groupe ${application === "cogeo" ? "Cogeo" : "Planning"} de ${identifiant}`}
        className={CLASSE_SELECT}
        value={valeur ?? ""}
        disabled={modifierMutation.isPending}
        onChange={(e) =>
          modifier(
            { identifiant, [champ]: e.target.value === "" ? null : Number(e.target.value) },
            `Rattachement de ${identifiant} modifié.`
          )
        }
      >
        <option value="">Aucun</option>
        {groupes
          .filter((groupe) => groupe.application === application)
          .map((groupe) => (
            <option key={groupe.id} value={groupe.id}>
              {groupe.nom}
            </option>
          ))}
      </select>
    );
  }

  return (
    <section>
      <h2 className="mb-2 text-sm font-semibold">Rattachements</h2>
      {rattachementsQuery.isLoading && <output>Chargement…</output>}
      <Erreur erreur={rattachementsQuery.error} parDefaut="Le chargement des rattachements a échoué." />
      {rattachementsQuery.data && (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Compte</TableHead>
              <TableHead>Groupe Cogeo</TableHead>
              <TableHead>Groupe Planning</TableHead>
              <TableHead>Utilisateur Moduléo</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rattachementsQuery.data.map((rattachement) => {
              const { identifiant } = rattachement;
              const compte = comptes.get(identifiant);
              const nom = noms[identifiant] ?? "";
              return (
                <TableRow key={identifiant}>
                  <TableCell>{compte ? `${compte.prenom} ${compte.nom} (${identifiant})` : identifiant}</TableCell>
                  <TableCell>{choixGroupe(identifiant, "cogeo", rattachement.groupe_cogeo_id)}</TableCell>
                  <TableCell>{choixGroupe(identifiant, "planning", rattachement.groupe_planning_id)}</TableCell>
                  <TableCell>
                    <form
                      className="flex items-center gap-1"
                      onSubmit={(e) => {
                        e.preventDefault();
                        modifier(
                          { identifiant, utilisateur_moduleo: nom.trim() },
                          `${identifiant} rattaché à l'utilisateur Moduléo ${nom.trim()}.`
                        );
                      }}
                    >
                      <span className="w-12 text-xs text-muted-foreground">
                        {rattachement.id_utilisateur_moduleo ?? "aucun"}
                      </span>
                      <Input
                        aria-label={`Nom de l'utilisateur Moduléo de ${identifiant}`}
                        className="h-8 w-36"
                        placeholder="Nom Moduléo"
                        value={nom}
                        onChange={(e) => setNoms((actuels) => ({ ...actuels, [identifiant]: e.target.value }))}
                      />
                      <Button type="submit" size="sm" variant="outline" disabled={modifierMutation.isPending || !nom.trim()}>
                        Rattacher
                      </Button>
                      {rattachement.id_utilisateur_moduleo !== null && (
                        <Button
                          type="button"
                          size="sm"
                          variant="ghost"
                          disabled={modifierMutation.isPending}
                          onClick={() =>
                            modifier({ identifiant, utilisateur_moduleo: null }, `Utilisateur Moduléo de ${identifiant} retiré.`)
                          }
                        >
                          Retirer
                        </Button>
                      )}
                    </form>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      )}
    </section>
  );
}

function SectionJournal() {
  const journalQuery = useJournalModuleoQuery();

  return (
    <section>
      <h2 className="mb-2 text-sm font-semibold">Journal des droits Moduléo</h2>
      {journalQuery.isLoading && <output>Chargement…</output>}
      <Erreur erreur={journalQuery.error} parDefaut="Le chargement du journal a échoué." />
      {journalQuery.data &&
        (journalQuery.data.length === 0 ? (
          <p className="text-sm text-muted-foreground">Aucun changement enregistré.</p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Quand</TableHead>
                <TableHead>Qui</TableHead>
                <TableHead>Action</TableHead>
                <TableHead>Cible</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {journalQuery.data.map((evenement, index) => (
                <TableRow key={`${evenement.date}-${index}`}>
                  <TableCell>{new Date(evenement.date).toLocaleString("fr-FR")}</TableCell>
                  <TableCell>{evenement.admin}</TableCell>
                  <TableCell>{evenement.action}</TableCell>
                  <TableCell>{evenement.cible}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        ))}
    </section>
  );
}
