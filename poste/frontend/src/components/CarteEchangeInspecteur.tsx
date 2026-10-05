import { useState, type ReactNode } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { useInspecteurEchangeQuery, type InspecteurEchangeResume } from "@/hooks/useInspecteur";
import { messageErreur } from "@/lib/api";

// Même vocabulaire que Consommation.type_appel côté VM centrale (spec 1.3.0).
const LIBELLES_TYPE_APPEL: Record<string, string> = {
  chat: "Chat",
  titrage: "Titrage",
  resume_et_profil: "Résumé + profil",
  ocr: "OCR",
  vision: "Vision",
};

// Début exact du message système construit par
// vm_centrale.routers.conversations._message_systeme_piece_jointe : seul
// endroit d'où l'on peut lire le nom du fichier, l'API de l'inspecteur ne
// renvoyant que piece_jointe_id.
const _MOTIF_MESSAGE_SYSTEME_PIECE_JOINTE = /^Pièce jointe « (.+?) » du message que le compte vient d'envoyer/;

type ContenuPieceJointe = { type: "texte"; texte: string } | { type: "fichier"; urlDonnees: string };

interface CarteEchangeInspecteurProps {
  cleAdminVm: string;
  echange: InspecteurEchangeResume;
}

// Carte d'un échange technique (un appel Mistral, succès ou échec) dans le
// fil chronologique de l'inspecteur : remplace la bulle d'OngletChat, et se
// déplie pour montrer le payload envoyé et la réponse brute reçue.
export function CarteEchangeInspecteur({ cleAdminVm, echange }: Readonly<CarteEchangeInspecteurProps>) {
  const [deplie, setDeplie] = useState(false);
  const detailQuery = useInspecteurEchangeQuery(cleAdminVm, echange.id, deplie);
  const enEchec = echange.statut === "echec";
  const Chevron = deplie ? ChevronDown : ChevronRight;

  const erreurDetail = messageErreur(detailQuery.error, "Le chargement de l'échange a échoué. Réessayez plus tard.");

  return (
    <article className="rounded-md border bg-card text-sm">
      <button
        type="button"
        aria-expanded={deplie}
        onClick={() => setDeplie((valeur) => !valeur)}
        className="flex w-full items-center gap-3 px-3 py-2 text-left hover:bg-muted/50"
      >
        <Chevron className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
        <span className="font-medium">{LIBELLES_TYPE_APPEL[echange.type_appel] ?? echange.type_appel}</span>
        <Badge variant={enEchec ? "destructive" : "secondary"}>{enEchec ? "Échec" : "Succès"}</Badge>
        <span className="ml-auto text-xs text-muted-foreground">
          <time dateTime={echange.date_creation}>{new Date(echange.date_creation).toLocaleString()}</time>
        </span>
      </button>

      {deplie && (
        <div className="flex flex-col gap-3 border-t px-3 py-3">
          {detailQuery.isLoading && <output>Chargement…</output>}
          {erreurDetail && (
            <p role="alert" className="text-sm text-destructive">
              {erreurDetail}
            </p>
          )}
          {detailQuery.data && (
            <>
              <p className="text-xs text-muted-foreground">Modèle : {detailQuery.data.modele}</p>
              {detailQuery.data.erreur && (
                <Section titre="Erreur">
                  <BlocTexte className="text-destructive">{detailQuery.data.erreur}</BlocTexte>
                </Section>
              )}
              <Section titre="Payload envoyé">
                <ContenuPayload
                  payload={detailQuery.data.requete_payload}
                  pieceJointeId={detailQuery.data.piece_jointe_id}
                />
              </Section>
              <Section titre="Réponse brute reçue">
                {detailQuery.data.reponse_payload ? (
                  <BlocTexte>{JSON.stringify(detailQuery.data.reponse_payload, null, 2)}</BlocTexte>
                ) : (
                  <p className="text-xs text-muted-foreground">Aucune réponse reçue.</p>
                )}
              </Section>
            </>
          )}
        </div>
      )}
    </article>
  );
}

function Section({ titre, children }: Readonly<{ titre: string; children: ReactNode }>) {
  return (
    <section className="flex flex-col gap-1.5">
      <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{titre}</h3>
      {children}
    </section>
  );
}

function BlocTexte({ children, className }: Readonly<{ children: ReactNode; className?: string }>) {
  return (
    <pre
      className={`max-h-96 overflow-auto whitespace-pre-wrap break-words rounded-md bg-muted px-3 py-2 font-mono text-xs ${className ?? ""}`}
    >
      {children}
    </pre>
  );
}

interface ContenuPayloadProps {
  payload: Record<string, unknown>;
  pieceJointeId: number | null;
}

// Payload rendu fidèlement, sauf le contenu d'une pièce jointe (texte extrait
// injecté en message système ou renvoyé par l'outil, fichier en base64 pour
// OCR/vision) : affiché comme une référence cliquable plutôt qu'en clair
// (spec 1.3.0), le payload stocké restant, lui, intégral.
function ContenuPayload({ payload, pieceJointeId }: Readonly<ContenuPayloadProps>) {
  const { messages, document: documentOcr, ...reste } = payload;
  const urlDocument = urlDonneesDuDocument(documentOcr);
  const resteAffiche = urlDocument || documentOcr === undefined ? reste : { ...reste, document: documentOcr };

  return (
    <div className="flex flex-col gap-2">
      {Array.isArray(messages) &&
        messages.map((message, index) => (
          <MessagePayload key={index} message={message} pieceJointeId={pieceJointeId} />
        ))}
      {urlDocument && (
        <ReferencePieceJointe
          libelle={libellePieceJointe(null, pieceJointeId)}
          contenu={{ type: "fichier", urlDonnees: urlDocument }}
        />
      )}
      {Object.keys(resteAffiche).length > 0 && <BlocTexte>{JSON.stringify(resteAffiche, null, 2)}</BlocTexte>}
    </div>
  );
}

function MessagePayload({ message, pieceJointeId }: Readonly<{ message: unknown; pieceJointeId: number | null }>) {
  if (!estObjet(message)) {
    return <BlocTexte>{JSON.stringify(message, null, 2)}</BlocTexte>;
  }

  const { role, content, ...autresChamps } = message;
  return (
    <div className="flex flex-col gap-1 rounded-md border px-3 py-2">
      <span className="text-xs font-semibold">{String(role)}</span>
      <ContenuMessage role={String(role)} content={content} pieceJointeId={pieceJointeId} />
      {Object.keys(autresChamps).length > 0 && <BlocTexte>{JSON.stringify(autresChamps, null, 2)}</BlocTexte>}
    </div>
  );
}

function ContenuMessage({
  role,
  content,
  pieceJointeId,
}: Readonly<{ role: string; content: unknown; pieceJointeId: number | null }>) {
  if (typeof content === "string") {
    const correspondance = role === "system" ? _MOTIF_MESSAGE_SYSTEME_PIECE_JOINTE.exec(content) : null;
    if (correspondance) {
      return (
        <ReferencePieceJointe
          libelle={libellePieceJointe(correspondance[1], null)}
          contenu={{ type: "texte", texte: content }}
        />
      );
    }
    // Résultat de l'outil de relecture d'une pièce jointe hors fenêtre :
    // piece_jointe_id porte alors celle relue par l'outil (spec 1.3.0).
    if (role === "tool" && pieceJointeId !== null) {
      return (
        <ReferencePieceJointe
          libelle={libellePieceJointe(null, pieceJointeId)}
          contenu={{ type: "texte", texte: content }}
        />
      );
    }
    return <p className="whitespace-pre-wrap break-words">{content}</p>;
  }

  if (Array.isArray(content)) {
    return (
      <div className="flex flex-col gap-1">
        {content.map((partie, index) => (
          <PartieMessage key={index} partie={partie} pieceJointeId={pieceJointeId} />
        ))}
      </div>
    );
  }

  if (content === undefined || content === null) {
    return null;
  }
  return <BlocTexte>{JSON.stringify(content, null, 2)}</BlocTexte>;
}

// Parties `text`/`image_url` du payload vision
// (vm_centrale.analyse_pieces_jointes.image).
function PartieMessage({ partie, pieceJointeId }: Readonly<{ partie: unknown; pieceJointeId: number | null }>) {
  if (estObjet(partie) && partie.type === "text" && typeof partie.text === "string") {
    return <p className="whitespace-pre-wrap break-words">{partie.text}</p>;
  }
  if (estObjet(partie) && partie.type === "image_url") {
    const url = estObjet(partie.image_url) ? partie.image_url.url : partie.image_url;
    if (typeof url === "string" && url.startsWith("data:")) {
      return (
        <ReferencePieceJointe
          libelle={libellePieceJointe(null, pieceJointeId)}
          contenu={{ type: "fichier", urlDonnees: url }}
        />
      );
    }
  }
  return <BlocTexte>{JSON.stringify(partie, null, 2)}</BlocTexte>;
}

function ReferencePieceJointe({ libelle, contenu }: Readonly<{ libelle: string; contenu: ContenuPieceJointe }>) {
  const [texteVisible, setTexteVisible] = useState(false);

  function voir() {
    if (contenu.type === "fichier") {
      ouvrirUrlDonnees(contenu.urlDonnees);
    } else {
      setTexteVisible((valeur) => !valeur);
    }
  }

  return (
    <div className="flex flex-col gap-1">
      <p className="text-sm">
        Pièce jointe : {libelle} —{" "}
        <button type="button" className="text-primary hover:underline" onClick={voir}>
          {texteVisible ? "masquer" : "voir"}
        </button>
      </p>
      {contenu.type === "texte" && texteVisible && <BlocTexte>{contenu.texte}</BlocTexte>}
    </div>
  );
}

function libellePieceJointe(nomFichier: string | null, pieceJointeId: number | null): string {
  if (nomFichier) {
    return nomFichier;
  }
  return pieceJointeId === null ? "fichier envoyé" : `n° ${pieceJointeId}`;
}

function urlDonneesDuDocument(documentOcr: unknown): string | null {
  if (estObjet(documentOcr) && typeof documentOcr.document_url === "string" && documentOcr.document_url.startsWith("data:")) {
    return documentOcr.document_url;
  }
  return null;
}

// Les navigateurs bloquent l'ouverture directe d'une URL data: dans un
// nouvel onglet : conversion synchrone en Blob (dans le geste utilisateur,
// sinon window.open serait bloqué comme popup).
function ouvrirUrlDonnees(urlDonnees: string) {
  const separateur = urlDonnees.indexOf(",");
  const typeMime = urlDonnees.slice("data:".length, separateur).replace(";base64", "");
  const binaire = atob(urlDonnees.slice(separateur + 1));
  const octets = Uint8Array.from(binaire, (caractere) => caractere.codePointAt(0) ?? 0);
  const url = URL.createObjectURL(new Blob([octets], { type: typeMime }));
  window.open(url, "_blank", "noopener");
  // Laisse le temps au nouvel onglet de charger le Blob avant de le libérer.
  setTimeout(() => URL.revokeObjectURL(url), 60_000);
}

function estObjet(valeur: unknown): valeur is Record<string, unknown> {
  return typeof valeur === "object" && valeur !== null && !Array.isArray(valeur);
}
