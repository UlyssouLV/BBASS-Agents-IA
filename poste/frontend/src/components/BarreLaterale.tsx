import { Ellipsis, SquarePen } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import logoBbassAgentsIa from "@/assets/logo-bbass-agents-ia.jpg";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Sidebar, SidebarContent, SidebarFooter, SidebarHeader } from "@/components/ui/sidebar";
import {
  useConversationsQuery,
  useRenommerConversationMutation,
  useSupprimerConversationMutation,
} from "@/hooks/useConversations";
import type { Compte } from "@/hooks/useSession";
import { messageErreur } from "@/lib/api";
import { cn } from "@/lib/utils";

interface BarreLateraleProps {
  compte: Compte;
  conversationOuverteId: number | null;
  onSelectionnerConversation: (id: number | null) => void;
  onOuvrirProfil: () => void;
  onOuvrirPanelAdministration: () => void;
  conversationRecenteId: number | null;
  onAnimationTitreTerminee: () => void;
}

function initiales(compte: Compte): string {
  return `${compte.prenom.charAt(0)}${compte.nom.charAt(0)}`.toUpperCase();
}

const _INTERVALLE_ANIMATION_TITRE_MS = 30;

// Issue #83 : à la création d'une conversation, le titre renvoyé par l'API
// (titre auto généré côté VM, inchangé — voir docs/specs/v1.2.1-identite-
// visuelle-disposition.md) ne doit pas apparaître d'un bloc dans la
// sidebar : il s'écrit progressivement, caractère par caractère, une fois
// connu. `onTermine` bascule le parent hors du mode « conversation
// récente » une fois l'animation finie, pour qu'un renommage ultérieur
// n'affiche plus jamais cette animation sur cette ligne.
function TitreAnimeConversation({
  titre,
  onTermine,
}: Readonly<{ titre: string; onTermine: () => void }>) {
  const [longueurAffichee, setLongueurAffichee] = useState(0);
  const animationTermineeRef = useRef(false);

  useEffect(() => {
    if (longueurAffichee >= titre.length) {
      if (!animationTermineeRef.current) {
        animationTermineeRef.current = true;
        onTermine();
      }
      return;
    }
    const delai = window.setTimeout(
      () => setLongueurAffichee((longueur) => longueur + 1),
      _INTERVALLE_ANIMATION_TITRE_MS
    );
    return () => window.clearTimeout(delai);
  }, [longueurAffichee, titre, onTermine]);

  return <>{titre.slice(0, longueurAffichee)}</>;
}

// Structure permanente de l'écran Compte façon ChatGPT (issue #74) : reprend
// la liste des conversations et la création d'une nouvelle conversation
// qu'OngletChat gérait jusqu'ici dans sa propre colonne de gauche (voir
// docs/specs/v1.2.1-identite-visuelle-disposition.md). La puce compte en bas
// remplace l'ancien en-tête d'EcranCompte (identité, bouton Profil, et pour
// un compte administrateur le bouton Panel d'administration).
export function BarreLaterale({
  compte,
  conversationOuverteId,
  onSelectionnerConversation,
  onOuvrirProfil,
  onOuvrirPanelAdministration,
  conversationRecenteId,
  onAnimationTitreTerminee,
}: Readonly<BarreLateraleProps>) {
  const conversationsQuery = useConversationsQuery();
  const renommerConversationMutation = useRenommerConversationMutation();
  const supprimerConversationMutation = useSupprimerConversationMutation();

  // Renommage inline (remplace window.prompt, qui n'affiche pas de champ
  // utilisable) : le titre de la ligne devient un input tant que
  // renommageId correspond à cette conversation. fermetureManuelleRef évite
  // qu'onBlur ne rejoue la validation déjà faite par Entrée, et qu'il n'en
  // déclenche une après Escape (qui ne doit jamais enregistrer).
  const [renommageId, setRenommageId] = useState<number | null>(null);
  const [titreEnCours, setTitreEnCours] = useState("");
  const fermetureManuelleRef = useRef(false);

  // Bouton « … » masqué par défaut (voir group-hover ci-dessous) : reste
  // visible tant que son menu est ouvert, même si la souris quitte la ligne.
  const [menuOuvertId, setMenuOuvertId] = useState<number | null>(null);

  // Confirmation de suppression (issue #87) : remplace window.confirm, qui
  // n'affiche rien dans ce contexte (même défaut que window.prompt, déjà
  // contourné pour le renommage inline — voir #81). conversationASupprimerId
  // pilote l'ouverture d'un Dialog shadcn/ui ; null signifie fermé.
  const [conversationASupprimerId, setConversationASupprimerId] = useState<number | null>(null);

  const poleAgence = [compte.poles.join(", "), compte.agence].filter(Boolean).join(" — ");

  function commencerRenommage(conversation: { id: number; titre: string }) {
    setRenommageId(conversation.id);
    setTitreEnCours(conversation.titre);
  }

  function validerRenommage(id: number, titreActuel: string) {
    const nouveauTitre = titreEnCours.trim();
    setRenommageId(null);
    if (!nouveauTitre || nouveauTitre === titreActuel) {
      return;
    }
    renommerConversationMutation.mutate({ id, titre: nouveauTitre });
  }

  function annulerRenommage() {
    fermetureManuelleRef.current = true;
    setRenommageId(null);
  }

  function supprimerConversation(id: number) {
    supprimerConversationMutation.mutate(id, {
      onSuccess: () => {
        if (conversationOuverteId === id) {
          onSelectionnerConversation(null);
        }
      },
    });
  }

  function confirmerSuppression() {
    if (conversationASupprimerId !== null) {
      supprimerConversation(conversationASupprimerId);
    }
    setConversationASupprimerId(null);
  }

  const erreurConversations = messageErreur(
    conversationsQuery.error,
    "Le chargement des conversations a échoué. Réessayez plus tard."
  );

  return (
    <Sidebar>
      <SidebarHeader className="gap-3 px-2 pt-2 pb-3">
        <img
          src={logoBbassAgentsIa}
          alt="BBASS Agents IA"
          className="block h-auto w-full scale-105 object-contain object-left"
        />
        <Button type="button" size="sm" className="w-full" onClick={() => onSelectionnerConversation(null)}>
          <SquarePen aria-hidden="true" />
          Nouvelle conversation
        </Button>
      </SidebarHeader>

      <SidebarContent className="pt-8">
        <h2 className="mb-2 text-sm font-semibold">Conversations</h2>
        {erreurConversations && (
          <p role="alert" className="mb-2 text-sm text-destructive">
            {erreurConversations}
          </p>
        )}
        {conversationsQuery.isLoading && <output className="mb-2 block text-sm text-muted-foreground">Chargement…</output>}
        <ul className="flex flex-col gap-1">
          {conversationsQuery.data?.map((conversation) => {
            const estOuverte = conversation.id === conversationOuverteId;
            const menuOuvert = menuOuvertId === conversation.id;
            return (
              <li
                key={conversation.id}
                className={cn(
                  "group flex items-center gap-1 rounded-sm",
                  estOuverte && "bg-secondary text-secondary-foreground"
                )}
              >
                {renommageId === conversation.id ? (
                  <input
                    ref={(element) => element?.focus()}
                    value={titreEnCours}
                    onChange={(evenement) => setTitreEnCours(evenement.target.value)}
                    onBlur={() => {
                      if (fermetureManuelleRef.current) {
                        fermetureManuelleRef.current = false;
                        return;
                      }
                      validerRenommage(conversation.id, conversation.titre);
                    }}
                    onKeyDown={(evenement) => {
                      if (evenement.key === "Enter") {
                        fermetureManuelleRef.current = true;
                        validerRenommage(conversation.id, conversation.titre);
                      } else if (evenement.key === "Escape") {
                        annulerRenommage();
                      }
                    }}
                    className="flex-1 truncate rounded-sm bg-background px-1.5 py-1 text-left text-sm text-foreground outline-none ring-1 ring-ring"
                  />
                ) : (
                  <button
                    type="button"
                    className={
                      estOuverte
                        ? "line-clamp-2 flex-1 break-words rounded-sm px-1.5 py-1 text-left text-sm"
                        : "line-clamp-2 flex-1 break-words rounded-sm px-1.5 py-1 text-left text-sm hover:bg-secondary/50"
                    }
                    onClick={() => onSelectionnerConversation(conversation.id)}
                  >
                    {conversation.id === conversationRecenteId ? (
                      <TitreAnimeConversation titre={conversation.titre} onTermine={onAnimationTitreTerminee} />
                    ) : (
                      conversation.titre
                    )}
                  </button>
                )}
                <DropdownMenu onOpenChange={(ouvert) => setMenuOuvertId(ouvert ? conversation.id : null)}>
                  <DropdownMenuTrigger asChild>
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      className={cn(
                        "size-7 shrink-0",
                        menuOuvert
                          ? "opacity-100"
                          : "opacity-0 group-hover:opacity-100 group-focus-within:opacity-100"
                      )}
                      aria-label="Actions de la conversation"
                    >
                      <Ellipsis aria-hidden="true" />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent
                    align="end"
                    onCloseAutoFocus={(evenement) => {
                      // Empêche Radix de rendre le focus au bouton « … » à
                      // la fermeture : sinon il entre en compétition avec le
                      // focus programmatique de l'input inline ouvert par
                      // Renommer (voir le ref de cet input, plus haut).
                      evenement.preventDefault();
                    }}
                  >
                    <DropdownMenuItem onSelect={() => commencerRenommage(conversation)}>
                      Renommer
                    </DropdownMenuItem>
                    <DropdownMenuItem
                      variant="destructive"
                      onSelect={() => setConversationASupprimerId(conversation.id)}
                    >
                      Supprimer
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              </li>
            );
          })}
        </ul>
      </SidebarContent>

      <SidebarFooter>
        <div className="flex items-center gap-2">
          <Avatar>
            <AvatarFallback>{initiales(compte)}</AvatarFallback>
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
      </SidebarFooter>

      <Dialog
        open={conversationASupprimerId !== null}
        onOpenChange={(ouvert) => {
          if (!ouvert) {
            setConversationASupprimerId(null);
          }
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Supprimer cette conversation ?</DialogTitle>
            <DialogDescription>
              Cette action est définitive et supprimera l'ensemble des messages de la conversation.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setConversationASupprimerId(null)}>
              Annuler
            </Button>
            <Button type="button" variant="destructive" onClick={confirmerSuppression}>
              Supprimer
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Sidebar>
  );
}
