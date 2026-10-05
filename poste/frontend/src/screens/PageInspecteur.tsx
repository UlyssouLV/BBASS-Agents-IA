import { useEffect, useState, type FormEvent } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { CarteEchangeInspecteur } from "@/components/CarteEchangeInspecteur";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import {
  CLE_INSPECTEUR,
  useInspecteurComptesQuery,
  useInspecteurConversationsQuery,
  useInspecteurEchangesQuery,
  type InspecteurConversation,
} from "@/hooks/useInspecteur";
import { ErreurApi, messageErreur } from "@/lib/api";
import { usePerfChargementPage } from "@/lib/instrumentationTemps";

interface Navigation {
  identifiantCompte: string | null;
  conversation: InspecteurConversation | null;
}

const _NAVIGATION_RACINE: Navigation = { identifiantCompte: null, conversation: null };

// Mode développeur (spec 1.3.0) : point d'entrée séparé de l'application
// principale (route /inspecteur, ouverte par Ctrl+Maj+D, voir App.tsx),
// trois niveaux en profondeur — comptes → conversations → fil des échanges
// avec Mistral. La Clé d'administration VM reste en mémoire de cet onglet
// seulement (jamais en localStorage), à ressaisir à chaque ouverture.
export function PageInspecteur() {
  const queryClient = useQueryClient();
  const [cleAdminVm, setCleAdminVm] = useState<string | null>(null);
  const [erreurCle, setErreurCle] = useState<string | null>(null);
  const [navigation, setNavigation] = useState<Navigation>(_NAVIGATION_RACINE);

  useEffect(() => {
    document.title = "Inspecteur des échanges — BBASS Agents IA";
  }, []);

  // Un 401 à n'importe quel niveau (clé refusée, ou session poste absente) :
  // retour à l'écran de saisie avec le message de la VM, sans garder en cache
  // ce qui a été chargé avec l'ancienne clé.
  function revenirALaSaisie(message: string) {
    queryClient.removeQueries({ queryKey: CLE_INSPECTEUR });
    setCleAdminVm(null);
    setNavigation(_NAVIGATION_RACINE);
    setErreurCle(message);
  }

  if (cleAdminVm === null) {
    return (
      <EcranCleInspecteur
        erreur={erreurCle}
        onValider={(cle) => {
          setErreurCle(null);
          setCleAdminVm(cle);
        }}
      />
    );
  }

  return (
    <main className="mx-auto flex h-svh w-full max-w-5xl flex-col px-6 py-6">
      <h1 className="mb-1 text-xl font-semibold">Inspecteur des échanges avec le modèle</h1>
      <nav aria-label="Fil d'Ariane" className="mb-4 flex flex-wrap items-center gap-1 text-sm text-muted-foreground">
        <button type="button" className="hover:underline" onClick={() => setNavigation(_NAVIGATION_RACINE)}>
          Comptes
        </button>
        {navigation.identifiantCompte && (
          <>
            <span aria-hidden="true">/</span>
            <button
              type="button"
              className="hover:underline"
              onClick={() => setNavigation({ identifiantCompte: navigation.identifiantCompte, conversation: null })}
            >
              {navigation.identifiantCompte}
            </button>
          </>
        )}
        {navigation.conversation && (
          <>
            <span aria-hidden="true">/</span>
            <span className="text-foreground">{navigation.conversation.titre}</span>
          </>
        )}
      </nav>

      {_niveau(cleAdminVm)}
    </main>
  );

  function _niveau(cle: string) {
    if (navigation.identifiantCompte && navigation.conversation) {
      return (
        <FilEchanges
          key={navigation.conversation.id}
          cleAdminVm={cle}
          conversationId={navigation.conversation.id}
          onCleRefusee={revenirALaSaisie}
        />
      );
    }
    if (navigation.identifiantCompte) {
      const identifiantCompte = navigation.identifiantCompte;
      return (
        <NiveauConversations
          cleAdminVm={cle}
          identifiantCompte={identifiantCompte}
          onChoisir={(conversation) => setNavigation({ identifiantCompte, conversation })}
          onCleRefusee={revenirALaSaisie}
        />
      );
    }
    return (
      <NiveauComptes
        cleAdminVm={cle}
        onChoisir={(identifiantCompte) => setNavigation({ identifiantCompte, conversation: null })}
        onCleRefusee={revenirALaSaisie}
      />
    );
  }
}

interface EcranCleInspecteurProps {
  erreur: string | null;
  onValider: (cle: string) => void;
}

// Même champ, même libellé et même comportement que la saisie de la Clé
// d'administration VM d'OngletComptes (FormulaireStatutAdmin) : rien n'est
// chargé avant qu'elle soit saisie.
function EcranCleInspecteur({ erreur, onValider }: Readonly<EcranCleInspecteurProps>) {
  const [saisie, setSaisie] = useState("");

  function gererEnvoi(evenement: FormEvent<HTMLFormElement>) {
    evenement.preventDefault();
    onValider(saisie);
  }

  return (
    <main className="mx-auto mt-24 w-full max-w-sm">
      <h1 className="mb-2 text-xl font-semibold">Inspecteur des échanges avec le modèle</h1>
      <p className="mb-6 text-sm text-muted-foreground">La Clé d'administration VM est requise pour ouvrir le mode développeur.</p>
      <form onSubmit={gererEnvoi} className="flex flex-col gap-4">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="inspecteur-cle">Clé d'administration VM</Label>
          <Input
            id="inspecteur-cle"
            type="password"
            required
            autoFocus
            value={saisie}
            onChange={(evenement) => setSaisie(evenement.target.value)}
          />
        </div>
        <Button type="submit">Ouvrir l'inspecteur</Button>
        {erreur && (
          <p role="alert" className="text-sm text-destructive">
            {erreur}
          </p>
        )}
      </form>
    </main>
  );
}

function useRetourSurCleRefusee(erreur: unknown, onCleRefusee: (message: string) => void) {
  useEffect(() => {
    if (erreur instanceof ErreurApi && erreur.status === 401) {
      onCleRefusee(erreur.message);
    }
  }, [erreur, onCleRefusee]);
}

function EnTeteNiveau({ titre, enCours, onRafraichir }: Readonly<{ titre: string; enCours: boolean; onRafraichir: () => void }>) {
  return (
    <div className="mb-4 flex items-center justify-between">
      <h2 className="text-sm font-semibold">{titre}</h2>
      <Button type="button" size="sm" variant="outline" disabled={enCours} onClick={onRafraichir}>
        Rafraîchir
      </Button>
    </div>
  );
}

interface NiveauComptesProps {
  cleAdminVm: string;
  onChoisir: (identifiantCompte: string) => void;
  onCleRefusee: (message: string) => void;
}

function NiveauComptes({ cleAdminVm, onChoisir, onCleRefusee }: Readonly<NiveauComptesProps>) {
  const comptesQuery = useInspecteurComptesQuery(cleAdminVm);
  useRetourSurCleRefusee(comptesQuery.error, onCleRefusee);
  usePerfChargementPage("inspecteur", !comptesQuery.isLoading);

  const erreur = messageErreur(comptesQuery.error, "Le chargement des comptes a échoué. Réessayez plus tard.");

  return (
    <div>
      <EnTeteNiveau titre="Comptes" enCours={comptesQuery.isFetching} onRafraichir={() => comptesQuery.refetch()} />
      {comptesQuery.isLoading && <output>Chargement…</output>}
      {erreur && (
        <p role="alert" className="mb-2 text-sm text-destructive">
          {erreur}
        </p>
      )}
      {comptesQuery.data?.length === 0 && (
        <p className="text-sm text-muted-foreground">Aucun compte n'a encore de conversation.</p>
      )}
      {comptesQuery.data && comptesQuery.data.length > 0 && (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Identifiant</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {comptesQuery.data.map((compte) => (
              <TableRow key={compte.identifiant_compte}>
                <TableCell>
                  <button type="button" className="hover:underline" onClick={() => onChoisir(compte.identifiant_compte)}>
                    {compte.identifiant_compte}
                  </button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </div>
  );
}

interface NiveauConversationsProps {
  cleAdminVm: string;
  identifiantCompte: string;
  onChoisir: (conversation: InspecteurConversation) => void;
  onCleRefusee: (message: string) => void;
}

function NiveauConversations({ cleAdminVm, identifiantCompte, onChoisir, onCleRefusee }: Readonly<NiveauConversationsProps>) {
  const conversationsQuery = useInspecteurConversationsQuery(cleAdminVm, identifiantCompte);
  useRetourSurCleRefusee(conversationsQuery.error, onCleRefusee);

  const erreur = messageErreur(conversationsQuery.error, "Le chargement des conversations a échoué. Réessayez plus tard.");

  return (
    <div>
      <EnTeteNiveau
        titre={`Conversations de ${identifiantCompte}`}
        enCours={conversationsQuery.isFetching}
        onRafraichir={() => conversationsQuery.refetch()}
      />
      {conversationsQuery.isLoading && <output>Chargement…</output>}
      {erreur && (
        <p role="alert" className="mb-2 text-sm text-destructive">
          {erreur}
        </p>
      )}
      {conversationsQuery.data?.length === 0 && (
        <p className="text-sm text-muted-foreground">Aucune conversation pour ce compte.</p>
      )}
      {conversationsQuery.data && conversationsQuery.data.length > 0 && (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Titre</TableHead>
              <TableHead>Créée le</TableHead>
              <TableHead>Dernière activité</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {conversationsQuery.data.map((conversation) => (
              <TableRow key={conversation.id}>
                <TableCell>
                  <button type="button" className="text-left hover:underline" onClick={() => onChoisir(conversation)}>
                    {conversation.titre}
                  </button>
                </TableCell>
                <TableCell>{new Date(conversation.date_creation).toLocaleString()}</TableCell>
                <TableCell>{new Date(conversation.date_derniere_activite).toLocaleString()}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </div>
  );
}

interface FilEchangesProps {
  cleAdminVm: string;
  conversationId: number;
  onCleRefusee: (message: string) => void;
}

// Même fil que celui d'OngletChat (role="log", colonne défilante), où chaque
// bulle de message est remplacée par une carte d'échange technique.
function FilEchanges({ cleAdminVm, conversationId, onCleRefusee }: Readonly<FilEchangesProps>) {
  const echangesQuery = useInspecteurEchangesQuery(cleAdminVm, conversationId);
  useRetourSurCleRefusee(echangesQuery.error, onCleRefusee);
  usePerfChargementPage("inspecteur-fil", !echangesQuery.isLoading);

  const erreur = messageErreur(echangesQuery.error, "Le chargement des échanges a échoué. Réessayez plus tard.");

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <EnTeteNiveau titre="Échanges avec le modèle" enCours={echangesQuery.isFetching} onRafraichir={() => echangesQuery.refetch()} />
      {echangesQuery.isLoading && <output>Chargement…</output>}
      {erreur && (
        <p role="alert" className="mb-2 text-sm text-destructive">
          {erreur}
        </p>
      )}
      {echangesQuery.data?.length === 0 && (
        <p className="text-sm text-muted-foreground">Aucun échange capturé pour cette conversation.</p>
      )}
      {echangesQuery.data && echangesQuery.data.length > 0 && (
        <div role="log" className="flex min-h-0 flex-1 flex-col gap-2 overflow-y-auto">
          {echangesQuery.data.map((echange) => (
            <CarteEchangeInspecteur key={echange.id} cleAdminVm={cleAdminVm} echange={echange} />
          ))}
        </div>
      )}
    </div>
  );
}
