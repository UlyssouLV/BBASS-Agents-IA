import { Ellipsis } from "lucide-react";

import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
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

interface BarreLateraleProps {
  compte: Compte;
  conversationOuverteId: number | null;
  onSelectionnerConversation: (id: number | null) => void;
  onOuvrirProfil: () => void;
  onOuvrirPanelAdministration: () => void;
}

function initiales(compte: Compte): string {
  return `${compte.prenom.charAt(0)}${compte.nom.charAt(0)}`.toUpperCase();
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
}: Readonly<BarreLateraleProps>) {
  const conversationsQuery = useConversationsQuery();
  const renommerConversationMutation = useRenommerConversationMutation();
  const supprimerConversationMutation = useSupprimerConversationMutation();

  const poleAgence = [compte.poles.join(", "), compte.agence].filter(Boolean).join(" — ");

  function renommerConversation(id: number, titreActuel: string) {
    const nouveauTitre = window.prompt("Nouveau titre de la conversation :", titreActuel);
    if (!nouveauTitre?.trim() || nouveauTitre === titreActuel) {
      return;
    }
    renommerConversationMutation.mutate({ id, titre: nouveauTitre });
  }

  function supprimerConversation(id: number) {
    if (!window.confirm("Supprimer définitivement cette conversation ?")) {
      return;
    }
    supprimerConversationMutation.mutate(id, {
      onSuccess: () => {
        if (conversationOuverteId === id) {
          onSelectionnerConversation(null);
        }
      },
    });
  }

  const erreurConversations = messageErreur(
    conversationsQuery.error,
    "Le chargement des conversations a échoué. Réessayez plus tard."
  );

  return (
    <Sidebar>
      <SidebarHeader>
        <Button type="button" variant="outline" size="sm" onClick={() => onSelectionnerConversation(null)}>
          Nouvelle conversation
        </Button>
      </SidebarHeader>

      <SidebarContent>
        <h2 className="mb-2 text-sm font-semibold">Conversations</h2>
        {erreurConversations && (
          <p role="alert" className="mb-2 text-sm text-destructive">
            {erreurConversations}
          </p>
        )}
        {conversationsQuery.isLoading && <output className="mb-2 block text-sm text-muted-foreground">Chargement…</output>}
        <ul className="flex flex-col gap-1">
          {conversationsQuery.data?.map((conversation) => (
            <li key={conversation.id} className="flex items-center gap-1">
              <button
                type="button"
                className={
                  conversation.id === conversationOuverteId
                    ? "flex-1 truncate rounded-sm bg-secondary px-1.5 py-1 text-left text-sm text-secondary-foreground"
                    : "flex-1 truncate rounded-sm px-1.5 py-1 text-left text-sm hover:bg-secondary/50"
                }
                onClick={() => onSelectionnerConversation(conversation.id)}
              >
                {conversation.titre}
              </button>
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="size-7 shrink-0"
                    aria-label="Actions de la conversation"
                  >
                    <Ellipsis aria-hidden="true" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  <DropdownMenuItem
                    onSelect={() => renommerConversation(conversation.id, conversation.titre)}
                  >
                    Renommer
                  </DropdownMenuItem>
                  <DropdownMenuItem
                    variant="destructive"
                    onSelect={() => supprimerConversation(conversation.id)}
                  >
                    Supprimer
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </li>
          ))}
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
    </Sidebar>
  );
}
