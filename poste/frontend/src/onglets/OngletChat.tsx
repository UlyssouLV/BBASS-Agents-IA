import {
  createContext,
  useContext,
  useEffect,
  useRef,
  useState,
  type DragEvent,
  type FormEvent,
  type ReactNode,
} from "react";
import {
  Check,
  Code2,
  Copy,
  ExternalLink,
  File,
  FileImage,
  FileSpreadsheet,
  FileText,
  FileType,
  Loader2,
  Paperclip,
  X,
  type LucideIcon,
} from "lucide-react";
import { Highlight, themes } from "prism-react-renderer";
import * as Prism from "prismjs";
import grammairesPrismBrut from "prismjs/components.json";
import Markdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";

import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  useConversationQuery,
  useCreerConversationMutation,
  useEnvoyerMessageMutation,
  type Message,
} from "@/hooks/useConversations";
import { messageErreur } from "@/lib/api";
import { cn } from "@/lib/utils";

// Mêmes extensions/types qu'app.js (formulaireNouvelleConversation /
// formulaireChat) : la VM centrale n'accepte pas d'autres pièces jointes
// (spec 1.1.2).
const TYPES_PIECE_JOINTE_ACCEPTES = ".pdf,.docx,.xlsx,image/jpeg,image/png,image/webp,image/gif";

// Issue #77 : icône affichée sous le champ de saisie une fois un fichier
// sélectionné, selon son type (déduit du nom de fichier pour PDF/Word/Excel,
// du type MIME pour les images — même distinction que
// TYPES_PIECE_JOINTE_ACCEPTES ci-dessus).
function typePieceJointe(fichier: File): "pdf" | "word" | "excel" | "image" | "autre" {
  if (fichier.type.startsWith("image/")) {
    return "image";
  }
  const nom = fichier.name.toLowerCase();
  if (nom.endsWith(".pdf")) {
    return "pdf";
  }
  if (nom.endsWith(".docx")) {
    return "word";
  }
  if (nom.endsWith(".xlsx")) {
    return "excel";
  }
  return "autre";
}

const ICONES_PIECE_JOINTE: Record<ReturnType<typeof typePieceJointe>, LucideIcon> = {
  pdf: FileText,
  word: FileType,
  excel: FileSpreadsheet,
  image: FileImage,
  autre: File,
};

function IconePieceJointe({ fichier, className }: Readonly<{ fichier: File; className?: string }>) {
  const Icone = ICONES_PIECE_JOINTE[typePieceJointe(fichier)];
  return <Icone className={className} aria-hidden="true" />;
}

interface OngletChatProps {
  conversationOuverteId: number | null;
  onConversationCreee: (id: number) => void;
}

// Issue #77 : la pièce jointe (optionnelle) n'est plus déposée via un champ
// <input type="file"> visible en permanence sous le champ de message, mais
// via une icône trombone intégrée au champ de saisie (clic) et le
// glisser-déposer sur ce même champ. Le fichier retenu est ensuite affiché
// sous le champ avec une icône selon son type et un moyen de le retirer.
function ChampMessageAvecPieceJointe({
  id,
  label,
  valeur,
  onChange,
  fichier,
  onFichierChange,
  disabled,
}: Readonly<{
  id: string;
  label: string;
  valeur: string;
  onChange: (valeur: string) => void;
  fichier: File | null;
  onFichierChange: (fichier: File | null) => void;
  disabled: boolean;
}>) {
  const refFichier = useRef<HTMLInputElement>(null);
  const [zoneDepotActive, setZoneDepotActive] = useState(false);

  function gererDepot(evenement: DragEvent<HTMLDivElement>) {
    evenement.preventDefault();
    setZoneDepotActive(false);
    const depose = evenement.dataTransfer.files?.[0];
    if (depose) {
      onFichierChange(depose);
    }
  }

  return (
    <div className="flex flex-col gap-1.5">
      <Label htmlFor={id} className="sr-only">
        {label}
      </Label>
      <div
        className={cn(
          "relative rounded-2xl transition-colors",
          zoneDepotActive && "outline-2 outline-offset-2 outline-primary bg-primary/5"
        )}
        onDragOver={(evenement) => {
          if (disabled) {
            return;
          }
          evenement.preventDefault();
          setZoneDepotActive(true);
        }}
        onDragLeave={() => setZoneDepotActive(false)}
        onDrop={disabled ? undefined : gererDepot}
      >
        <Textarea
          id={id}
          autoComplete="off"
          required
          rows={3}
          value={valeur}
          onChange={(evenement) => onChange(evenement.target.value)}
          onKeyDown={(evenement) => {
            // Issue #78 : Entrée seule soumet le formulaire (comme le
            // bouton « Envoyer » retiré ci-dessous), Maj+Entrée insère un
            // retour à la ligne (comportement par défaut du textarea, donc
            // pas de preventDefault dans ce cas).
            if (evenement.key === "Enter" && !evenement.shiftKey) {
              evenement.preventDefault();
              evenement.currentTarget.form?.requestSubmit();
            }
          }}
          disabled={disabled}
          className="pr-12"
        />
        <input
          type="file"
          id={`${id}-piece-jointe`}
          accept={TYPES_PIECE_JOINTE_ACCEPTES}
          ref={refFichier}
          disabled={disabled}
          className="sr-only"
          aria-label="Joindre un fichier"
          onChange={(evenement) => {
            onFichierChange(evenement.target.files?.[0] ?? null);
            evenement.target.value = "";
          }}
        />
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className="absolute right-2 bottom-2"
          disabled={disabled}
          onClick={() => refFichier.current?.click()}
          aria-label="Joindre un fichier"
        >
          <Paperclip className="size-4" />
        </Button>
      </div>
      {fichier && (
        <div className="flex w-fit items-center gap-2 rounded-lg border bg-muted px-3 py-1.5 text-sm">
          <IconePieceJointe fichier={fichier} className="size-4 shrink-0 text-muted-foreground" />
          <span className="max-w-48 truncate">{fichier.name}</span>
          <button
            type="button"
            onClick={() => onFichierChange(null)}
            disabled={disabled}
            aria-label="Retirer la pièce jointe"
            className="text-muted-foreground hover:text-foreground disabled:pointer-events-none disabled:opacity-50"
          >
            <X className="size-3.5" />
          </button>
        </div>
      )}
    </div>
  );
}

// Issue #93, étendu lors de la validation manuelle de la 1.2.2
// (2026-10-05) : allowlist des composants Markdown autorisés dans la bulle
// de message assistant (spec #91, Solution volet 2) : gras, italique,
// listes (imbriquées ou non), paragraphes, tableaux (remark-gfm, sans quoi
// la syntaxe `|...|` n'est jamais reconnue comme un tableau et s'affiche
// telle quelle — marqueurs bruts — plutôt que d'être neutralisée), blocs
// de code et liens (en pastille séparée du texte, voir LienSource). Le
// reste (titres, citations) est neutralisé en bloc générique ci-dessous
// plutôt que simplement « déplié » (unwrapDisallowed) — un titre ou une
// citation dépliée perd son élément englobant et se retrouve orpheline,
// collée sans espacement au contenu précédent. Les balises purement
// inline une fois neutralisées (image, rayé GFM) restent dépliées via
// ELEMENTS_MARKDOWN_DEPLIES : elles finissent de toute façon à
// l'intérieur d'un bloc déjà espacé ; une case à cocher de liste de
// tâches GFM (`input`) n'a pas de contenu à déplier, elle disparaît
// simplement (ce n'est pas un type de bloc envisagé par cette allowlist).
// La mise en forme (espacement entre blocs, puces différenciées par
// niveau d'imbrication) est portée par la classe `.contenu-markdown` dans
// index.css plutôt que par des classes par composant : un rendu
// standardisé qui ne dépend ni de la réponse ni du modèle. Ce mapping
// reste le point d'extension naturel pour de futurs types de blocs (cf.
// feuille de route, section « Plus tard »). `skipHtml` sur <Markdown>
// ci-dessous neutralise le HTML brut (ex. `<br>`) : sans lui, un nœud
// HTML échappe à disallowedElements (ce n'est pas un élément du même
// type) et s'affiche tel quel, marqueurs bruts inclus.
function BlocMarkdownNeutralise({ children }: Readonly<{ children?: ReactNode }>) {
  return <div>{children}</div>;
}

// Issue #91/#93, ajusté après validation manuelle de la 1.2.2 : même fond
// que la bulle (bg-muted) sur toute la largeur, sans distinction d'en-tête
// ni marge interne généreuse, un tableau se fondait dans le reste du
// message plutôt que de se lire comme un tableau. `bg-background` tranche
// avec la bulle qui l'entoure. Premier essai d'en-tête en `bg-muted` : ce
// token est en réalité identique à `--secondary` et au fond de la bulle
// elle-même (voir index.css), donc toujours aucun contraste visible — l'en-
// tête utilise à la place une teinte anthracite (`--primary`) à faible
// opacité, propre au tableau et distincte des deux autres fonds.
function Tableau({ children }: Readonly<{ children?: ReactNode }>) {
  return (
    <div className="overflow-x-auto rounded-md border border-border bg-background">
      <table className="w-full border-collapse text-left text-sm">{children}</table>
    </div>
  );
}

function EnTeteCelluleTableau({ children }: Readonly<{ children?: ReactNode }>) {
  return <th className="border-b border-border bg-primary/10 px-3 py-2 font-semibold">{children}</th>;
}

function CelluleTableau({ children }: Readonly<{ children?: ReactNode }>) {
  return <td className="border-b border-border px-3 py-2 align-top">{children}</td>;
}

// Bouton « Copier » générique, en haut à droite d'un bloc au survol — même
// convention que le bouton « … » de BarreLaterale.tsx (opacity-0 +
// group-hover/group-focus-within). Pris isolément de BlocCode pour rester
// le point d'extension naturel de futurs types de blocs porteurs d'un
// contenu à copier intégralement (cellule de document, etc. — cf. feuille
// de route, section « Plus tard ») : il leur suffira de l'envelopper avec
// leur propre `obtenirTexte`, sans dupliquer l'affordance.
function BlocAvecBoutonCopier({
  children,
  obtenirTexte,
  classeBouton,
}: Readonly<{ children: ReactNode; obtenirTexte: () => string; classeBouton?: string }>) {
  const [copie, setCopie] = useState(false);

  async function copier() {
    try {
      await navigator.clipboard.writeText(obtenirTexte());
      setCopie(true);
      window.setTimeout(() => setCopie(false), 1500);
    } catch {
      // Presse-papiers indisponible (permissions, contexte non sécurisé) :
      // rien d'autre à faire, le bouton reste silencieusement sans effet.
    }
  }

  return (
    <div className="group relative">
      {children}
      <Button
        type="button"
        variant="ghost"
        size="icon"
        className={cn(
          "absolute right-1 top-1 size-6 opacity-0 group-hover:opacity-100 group-focus-within:opacity-100",
          classeBouton
        )}
        onClick={copier}
        aria-label="Copier"
      >
        {copie ? <Check className="size-3.5" aria-hidden="true" /> : <Copy className="size-3.5" aria-hidden="true" />}
      </Button>
    </div>
  );
}

// Un bloc de code (```…```, mdast "code") devient <pre><code>, du code
// inline (`…`) devient juste <code> : react-markdown n'expose pas de prop
// pour distinguer les deux au niveau du composant `code`, d'où ce contexte
// posé par BlocCode — lu par CodeEnLigne pour ne pas empiler deux styles
// de « boîte » (celle du bloc, puis celle du chip inline) l'un dans
// l'autre. Le texte à copier est lu depuis le DOM (`textContent` du
// <pre>) plutôt que reconstruit à partir de `children` (React, pas une
// chaîne) : fiable quel que soit l'imbrication de spans produite par une
// éventuelle coloration syntaxique future.
const DansBlocCodeContext = createContext(false);

// Issue #97 : au lieu d'une liste `LANGAGES_COLORES` maintenue à la main
// (une entrée + un import statique par langage, périmètre #95 limité à
// python/bash/json/yaml/sql), les quelque 290 grammaires du paquet sont
// enregistrées ici une fois pour toutes sous forme de chargeurs
// dynamiques : `import.meta.glob` les recense au build (Vite sait alors
// produire un chunk par fichier), mais un seul chargeur est réellement
// invoqué à l'exécution — celui du langage effectivement déclaré sur le
// fence d'un bloc donné (voir chargerGrammairePrism plus bas). Le motif
// d'exclusion écarte les variantes minifiées (`*.min.js`) dès cette étape
// de recensement : ne pas produire de chunk de build pour un fichier
// qu'aucun appel ne référencera jamais.
const CHARGEURS_GRAMMAIRE_PRISM = import.meta.glob([
  "/node_modules/prismjs/components/prism-*.js",
  "!**/*.min.js",
]);

function cheminGrammairePrism(identifiant: string): string {
  return `/node_modules/prismjs/components/prism-${identifiant}.js`;
}

interface MetaLangagePrism {
  require?: string | string[];
  alias?: string | string[];
}

// Métadonnées officielles de Prism (alias de langage, dépendances entre
// grammaires — ex. "tsx" requiert "jsx" puis "javascript" puis "clike")
// plutôt qu'une table ad hoc : ce fichier JSON est déjà présent dans le
// paquet prismjs (dépendance existante, cf. #95).
const META_LANGAGES_PRISM = (grammairesPrismBrut as { languages: Record<string, MetaLangagePrism> }).languages;

function normaliserEnListe(valeur: string | string[] | undefined): string[] {
  if (!valeur) {
    return [];
  }
  return Array.isArray(valeur) ? valeur : [valeur];
}

// Alias -> identifiant canonique (ex. "js" et "ts" -> "javascript"/
// "typescript", "html"/"xml"/"svg" -> "markup") : construit depuis
// META_LANGAGES_PRISM, pas à la main, pour rester synchronisé avec le
// paquet installé.
const CANONIQUE_PAR_ALIAS: ReadonlyMap<string, string> = (() => {
  const table = new Map<string, string>();
  for (const [identifiant, meta] of Object.entries(META_LANGAGES_PRISM)) {
    table.set(identifiant, identifiant);
    for (const alias of normaliserEnListe(meta.alias)) {
      table.set(alias, identifiant);
    }
  }
  return table;
})();

// Une grammaire Prism suppose souvent une autre déjà enregistrée (ex. php
// requiert markup-templating, qui requiert markup) : cette chaîne doit
// être chargée dans l'ordre, base d'abord, sous peine de laisser la
// grammaire finale s'étendre depuis un langage de base manquant.
function cheneDependances(identifiant: string, vus: Set<string> = new Set()): string[] {
  if (vus.has(identifiant)) {
    return [];
  }
  vus.add(identifiant);
  const requises = normaliserEnListe(META_LANGAGES_PRISM[identifiant]?.require).flatMap((requise) =>
    cheneDependances(requise, vus)
  );
  return [...requises, identifiant];
}

// Charge, dans l'ordre de dépendance, chaque grammaire de la chaîne pas
// encore enregistrée sur Prism. Lève dès qu'un maillon n'a pas de fichier
// correspondant dans le paquet : l'appelant retombe alors sur le rendu
// neutre (déjà affiché par défaut pendant le chargement).
async function chargerGrammairePrism(identifiant: string): Promise<void> {
  for (const etape of cheneDependances(identifiant)) {
    if (Prism.languages[etape]) {
      continue;
    }
    const chargeur = CHARGEURS_GRAMMAIRE_PRISM[cheminGrammairePrism(etape)];
    if (!chargeur) {
      throw new Error(`Aucune grammaire Prism pour « ${etape} ».`);
    }
    await chargeur();
  }
}

// Le langage déclaré sur le fence n'est lisible que sur le noeud hast du
// <pre> (son unique enfant `code` porte la classe "language-xxx") : une
// fois `children` rendu par react-markdown pour atteindre BlocCode, le
// composant `code` (CodeEnLigne) a déjà consommé et remplacé cette classe
// par la sienne. `node` (non typé ici : le type hast exact n'est pas
// exposé par react-markdown au-delà de `unknown`) est donc lu par
// inspection défensive plutôt que via `children`.
function noeudCodeDuBloc(noeudPre: unknown): unknown {
  const enfants = (noeudPre as { children?: unknown[] } | undefined)?.children;
  const premier = enfants?.[0];
  return (premier as { tagName?: string } | undefined)?.tagName === "code" ? premier : undefined;
}

function langueDeclareeDuBloc(noeudPre: unknown): string | null {
  const classes = (noeudCodeDuBloc(noeudPre) as { properties?: { className?: unknown } } | undefined)?.properties
    ?.className;
  const classe = Array.isArray(classes)
    ? classes.find((valeur): valeur is string => typeof valeur === "string" && valeur.startsWith("language-"))
    : undefined;
  return classe ? classe.slice("language-".length).toLowerCase() : null;
}

function texteBrutDuNoeud(noeud: unknown): string {
  const n = noeud as { type?: string; value?: unknown; children?: unknown[] } | undefined;
  if (n?.type === "text" && typeof n.value === "string") {
    return n.value;
  }
  return n?.children?.map(texteBrutDuNoeud).join("") ?? "";
}

// En-tête façon ChatGPT (icône + nom du langage déclaré sur le fence, tel
// quel) commune aux deux rendus ci-dessous : affichée que la coloration
// réussisse ou non, pour que seule la présence de couleur par token
// distingue un bloc couvert d'un bloc neutre, jamais la mise en page.
function EnTeteBlocCode({ langage }: Readonly<{ langage: string | null }>) {
  return (
    <div className="flex items-center gap-1.5 border-b border-white/10 px-2 py-1 text-[0.7rem] opacity-70">
      <Code2 className="size-3" aria-hidden="true" />
      {langage}
    </div>
  );
}

// Issue #97 : la coloration (thème `vsDark`) et le rendu neutre d'un
// langage non couvert partagent désormais le même fond sombre — un bloc
// de code a toujours la même apparence de base, langage reconnu ou non,
// seule la couleur par token distingue les deux (`themes.vsDark.plain`
// porte ce fond + cette couleur de texte par défaut, posé une fois sur le
// conteneur commun plutôt que dupliqué entre les deux rendus).
function BlocCode({ node, children }: Readonly<{ node?: unknown; children?: ReactNode }>) {
  const refPre = useRef<HTMLPreElement>(null);
  const langueDeclaree = langueDeclareeDuBloc(node);
  const canonique = langueDeclaree ? (CANONIQUE_PAR_ALIAS.get(langueDeclaree) ?? null) : null;
  const [grammairePrete, setGrammairePrete] = useState(false);

  useEffect(() => {
    setGrammairePrete(false);
    if (!canonique) {
      return;
    }
    if (Prism.languages[canonique]) {
      setGrammairePrete(true);
      return;
    }
    let annule = false;
    chargerGrammairePrism(canonique)
      .then(() => {
        if (!annule) {
          setGrammairePrete(true);
        }
      })
      .catch(() => {
        // Pas de grammaire Prism pour ce langage (ou un de ses prérequis) :
        // le bloc garde le rendu neutre, déjà affiché par défaut.
      });
    return () => {
      annule = true;
    };
  }, [canonique]);

  const corps =
    grammairePrete && canonique ? (
      <Highlight prism={Prism} code={texteBrutDuNoeud(noeudCodeDuBloc(node))} language={canonique} theme={themes.vsDark}>
        {({ className: classeColoration, style, tokens, getLineProps, getTokenProps }) => (
          <pre ref={refPre} className={cn("overflow-x-auto p-2 pr-8 font-mono text-xs", classeColoration)} style={style}>
            <code>
              {tokens.map((ligne, indexLigne) => (
                <span key={indexLigne} {...getLineProps({ line: ligne })}>
                  {ligne.map((jeton, indexJeton) => (
                    <span key={indexJeton} {...getTokenProps({ token: jeton })} />
                  ))}
                  {indexLigne < tokens.length - 1 ? "\n" : null}
                </span>
              ))}
            </code>
          </pre>
        )}
      </Highlight>
    ) : (
      <pre ref={refPre} className="overflow-x-auto p-2 pr-8 font-mono text-xs" style={themes.vsDark.plain}>
        {children}
      </pre>
    );

  return (
    <DansBlocCodeContext.Provider value={true}>
      <BlocAvecBoutonCopier
        obtenirTexte={() => refPre.current?.textContent ?? ""}
        classeBouton="text-white/70 hover:bg-white/10 hover:text-white"
      >
        <div className="overflow-hidden rounded-sm border border-border" style={themes.vsDark.plain}>
          <EnTeteBlocCode langage={langueDeclaree} />
          {corps}
        </div>
      </BlocAvecBoutonCopier>
    </DansBlocCodeContext.Provider>
  );
}

function CodeEnLigne({ children }: Readonly<{ children?: ReactNode }>) {
  const dansUnBloc = useContext(DansBlocCodeContext);
  if (dansUnBloc) {
    return <code className="font-mono text-xs">{children}</code>;
  }
  return (
    <code className="rounded-sm border border-border bg-background px-1 py-0.5 font-mono text-[0.85em]">
      {children}
    </code>
  );
}

// Un lien n'est plus neutralisé en texte brut : le texte de l'ancre reste
// du texte normal (jamais souligné/bleu comme un lien classique, pour ne
// pas laisser croire que toute la phrase est cliquable), suivi d'une
// pastille séparée — seul élément réellement cliquable, même esprit que
// les bulles de citation de source d'autres assistants. `rel`
// noopener+noreferrer et le `urlTransform` par défaut de react-markdown
// (actif tant qu'on ne le surcharge pas ici) protègent contre les schémas
// d'URL dangereux (`javascript:`, etc.).
function LienSource({ href, children }: Readonly<{ href?: string; children?: ReactNode }>) {
  if (!href) {
    return <>{children}</>;
  }
  return (
    <>
      {children}
      <a
        href={href}
        target="_blank"
        rel="noopener noreferrer"
        className="ms-1 inline-flex size-4 translate-y-[-1px] items-center justify-center rounded-full bg-primary/10 align-middle text-primary hover:bg-primary/20"
        aria-label={`Ouvrir la source : ${href}`}
      >
        <ExternalLink className="size-2.5" aria-hidden="true" />
      </a>
    </>
  );
}

const COMPOSANTS_MARKDOWN_MESSAGE: Components = {
  h1: BlocMarkdownNeutralise,
  h2: BlocMarkdownNeutralise,
  h3: BlocMarkdownNeutralise,
  h4: BlocMarkdownNeutralise,
  h5: BlocMarkdownNeutralise,
  h6: BlocMarkdownNeutralise,
  blockquote: BlocMarkdownNeutralise,
  table: Tableau,
  th: EnTeteCelluleTableau,
  td: CelluleTableau,
  pre: BlocCode,
  code: CodeEnLigne,
  a: LienSource,
};
const ELEMENTS_MARKDOWN_DEPLIES = ["hr", "img", "del", "input"];

function ContenuMessageAssistant({ texte }: Readonly<{ texte: string }>) {
  return (
    <div className="contenu-markdown">
      <Markdown
        skipHtml
        remarkPlugins={[remarkGfm]}
        components={COMPOSANTS_MARKDOWN_MESSAGE}
        disallowedElements={ELEMENTS_MARKDOWN_DEPLIES}
        unwrapDisallowed
      >
        {texte}
      </Markdown>
    </div>
  );
}

// Issue #84 : le message du collaborateur ne doit pas apparaître d'un bloc
// en haut à droite de la conversation ; il glisse depuis la zone de saisie (juste en
// dessous) vers sa place définitive. requestAnimationFrame plutôt qu'un
// montage direct en position finale : le navigateur doit peindre l'état
// initial (translaté, transparent) avant que la transition CSS vers l'état
// final ne parte, sinon les deux états se confondent en un seul rendu.
function BulleMessageEnvoye({ texte }: Readonly<{ texte: string }>) {
  const [arrivee, setArrivee] = useState(false);

  useEffect(() => {
    const id = window.requestAnimationFrame(() => setArrivee(true));
    return () => window.cancelAnimationFrame(id);
  }, []);

  return (
    <p
      className={cn(
        "self-end rounded-md bg-primary px-3 py-1.5 text-sm text-primary-foreground transition-all duration-300 ease-out",
        arrivee ? "translate-y-0 opacity-100" : "translate-y-4 opacity-0"
      )}
    >
      {texte}
    </p>
  );
}

const _INTERVALLE_ANIMATION_FRAPPE_MS = 20;
// Nombre d'étapes cible pour parcourir tout le texte : un pas fixe (comme
// TitreAnimeConversation dans BarreLaterale.tsx) prendrait plusieurs
// secondes sur une réponse longue (contrainte 1.2.1 : « rythme soutenu, pas
// trop lent »). Le nombre de caractères révélés par étape est donc calculé
// pour que l'animation dure toujours environ le même temps, quelle que
// soit la longueur du texte déjà reçu (pas de streaming HTTP, voir issue).
const _NB_ETAPES_ANIMATION_FRAPPE = 60;

// Écrit `texte` progressivement, comme si l'Agent tapait sa réponse.
function TexteAnimeReponse({ texte, onTermine }: Readonly<{ texte: string; onTermine: () => void }>) {
  const [longueurAffichee, setLongueurAffichee] = useState(0);
  const animationTermineeRef = useRef(false);
  const caracteresParEtape = Math.max(1, Math.ceil(texte.length / _NB_ETAPES_ANIMATION_FRAPPE));

  useEffect(() => {
    if (longueurAffichee >= texte.length) {
      if (!animationTermineeRef.current) {
        animationTermineeRef.current = true;
        onTermine();
      }
      return;
    }
    const delai = window.setTimeout(
      () => setLongueurAffichee((longueur) => Math.min(texte.length, longueur + caracteresParEtape)),
      _INTERVALLE_ANIMATION_FRAPPE_MS
    );
    return () => window.clearTimeout(delai);
  }, [longueurAffichee, texte, caracteresParEtape, onTermine]);

  return <ContenuMessageAssistant texte={texte.slice(0, longueurAffichee)} />;
}

// Réécriture React de la section #onglet-chat d'app.js : ne porte plus que
// la conversation ouverte (nouvelle conversation ou conversation existante) — la
// liste des conversations et sa création sont montées dans la sidebar
// permanente de l'écran Compte depuis le ticket #74 (voir
// BarreLaterale.tsx et docs/specs/v1.2.1-identite-visuelle-disposition.md),
// `conversationOuverteId` devenant un état partagé porté par EcranCompte.
// Issue #76 : écran de composition centré (accroche + textarea partagé) ;
// les mutations TanStack Query restent inchangées.
//
// Issue #84 : le premier envoi et les envois suivants ne doivent plus
// attendre la réponse d'un bloc. `envoiEnCours` porte l'état visuel de la
// conversation pendant qu'une réponse est en vol, indépendamment de l'accroche ou de la
// conversation ouverte :
// - "attente" : la VM n'a pas encore répondu (indicateur « Réflexion… »).
// - "frappe"  : la réponse est connue et s'écrit progressivement (voir
//   TexteAnimeReponse ci-dessus).
// - "termine" : la frappe est finie ; on attend que `conversationQuery`
//   (invalidée par la mutation) rattrape le nouveau tour avant de rebasculer
//   sur ses données, pour ne jamais faire disparaître puis réapparaître le
//   message pendant que la requête de fond est encore en vol.
// `messagesAvantEnvoiRef` fige la liste affichée avant cet envoi (vide pour
// une toute nouvelle conversation) : tant qu'`envoiEnCours` n'est pas nul,
// la conversation se construit à partir de ce figé + des bulles optimistes plutôt
// que des données live, qui peuvent se mettre à jour avant la fin de
// l'animation.
type PhaseEnvoi = "attente" | "frappe" | "termine";

interface EnvoiEnCours {
  message: string;
  phase: PhaseEnvoi;
  reponse: string;
}

export function OngletChat({ conversationOuverteId, onConversationCreee }: Readonly<OngletChatProps>) {
  const [champNouveauMessage, setChampNouveauMessage] = useState("");
  const [champMessage, setChampMessage] = useState("");
  const [fichierNouvelleConversation, setFichierNouvelleConversation] = useState<File | null>(null);
  const [fichierMessage, setFichierMessage] = useState<File | null>(null);
  const [envoiEnCours, setEnvoiEnCours] = useState<EnvoiEnCours | null>(null);
  const messagesAvantEnvoiRef = useRef<Message[]>([]);

  const conversationQuery = useConversationQuery(conversationOuverteId);
  const creerConversationMutation = useCreerConversationMutation();
  const envoyerMessageMutation = useEnvoyerMessageMutation();

  // Une fois la frappe terminée, rebascule sur les données live dès qu'elles
  // contiennent bien ce tour (message + réponse), sans attendre davantage :
  // évite qu'une conversation déjà à jour reste figée sur l'état optimiste.
  useEffect(() => {
    if (envoiEnCours?.phase !== "termine") {
      return;
    }
    const messages = conversationQuery.data?.messages;
    if (messages && messages.length >= messagesAvantEnvoiRef.current.length + 2) {
      setEnvoiEnCours(null);
    }
  }, [envoiEnCours, conversationQuery.data]);

  function gererEnvoiNouvelleConversation(evenement: FormEvent<HTMLFormElement>) {
    evenement.preventDefault();

    const message = champNouveauMessage;
    const fichier = fichierNouvelleConversation;
    if (!message.trim() || creerConversationMutation.isPending) {
      return;
    }
    creerConversationMutation.reset();

    messagesAvantEnvoiRef.current = [];
    setEnvoiEnCours({ message, phase: "attente", reponse: "" });
    setChampNouveauMessage("");

    creerConversationMutation.mutate(
      {
        message,
        fichier,
        cleIdempotence: crypto.randomUUID(),
      },
      {
        onSuccess: (donnees) => {
          setFichierNouvelleConversation(null);
          setEnvoiEnCours({ message, phase: "frappe", reponse: donnees.reponse });
          onConversationCreee(donnees.conversation.id);
        },
        onError: () => {
          setEnvoiEnCours(null);
          setChampNouveauMessage(message);
        },
      }
    );
  }

  function gererEnvoiMessage(evenement: FormEvent<HTMLFormElement>) {
    evenement.preventDefault();

    const message = champMessage;
    const fichier = fichierMessage;
    if (!message.trim() || conversationOuverteId === null || envoyerMessageMutation.isPending) {
      return;
    }
    envoyerMessageMutation.reset();

    messagesAvantEnvoiRef.current = conversationQuery.data?.messages ?? [];
    setEnvoiEnCours({ message, phase: "attente", reponse: "" });
    setChampMessage("");

    envoyerMessageMutation.mutate(
      {
        conversationId: conversationOuverteId,
        message,
        fichier,
        cleIdempotence: crypto.randomUUID(),
      },
      {
        onSuccess: (donnees) => {
          setFichierMessage(null);
          setEnvoiEnCours({ message, phase: "frappe", reponse: donnees.reponse });
        },
        onError: () => {
          setEnvoiEnCours(null);
          setChampMessage(message);
        },
      }
    );
  }

  // Issue #84 : l'accroche ne s'affiche que si rien n'a encore été envoyé —
  // dès la soumission du premier message, on bascule sur le fil (avec les
  // bulles optimistes ci-dessous) sans attendre la réponse de la VM.
  const brouillonActif = conversationOuverteId === null && envoiEnCours === null;
  const messagesAffiches: Message[] =
    envoiEnCours !== null ? messagesAvantEnvoiRef.current : conversationQuery.data?.messages ?? [];

  const erreurConversationOuverte = messageErreur(
    conversationQuery.error,
    "L'ouverture de la conversation a échoué. Réessayez plus tard."
  );
  const erreurNouvelleConversation = messageErreur(
    creerConversationMutation.error,
    "La création de la conversation a échoué. Réessayez plus tard."
  );
  const erreurEnvoiMessage = messageErreur(
    envoyerMessageMutation.error,
    "L'envoi du message a échoué. Réessayez plus tard."
  );

  return (
    <div className="flex min-h-0 min-w-0 flex-1 flex-col">
      {brouillonActif ? (
        <div className="flex flex-1 flex-col items-center justify-center">
          <div className="w-full max-w-2xl">
            <h2 className="mb-6 text-center text-2xl font-semibold tracking-tight">Comment puis-je vous aider ?</h2>
            <form onSubmit={gererEnvoiNouvelleConversation} className="flex flex-col gap-3">
              <ChampMessageAvecPieceJointe
                id="nouveau-message-conversation"
                label="Premier message"
                valeur={champNouveauMessage}
                onChange={setChampNouveauMessage}
                fichier={fichierNouvelleConversation}
                onFichierChange={setFichierNouvelleConversation}
                disabled={creerConversationMutation.isPending}
              />
              {creerConversationMutation.data?.pieceJointeEchecAnalyse && (
                <output className="text-sm text-muted-foreground">
                  L'IA n'a pas pu analyser la pièce jointe « {creerConversationMutation.data.pieceJointeNomFichier} ».
                </output>
              )}
              {erreurNouvelleConversation && (
                <p role="alert" className="text-sm text-destructive">
                  {erreurNouvelleConversation}
                </p>
              )}
            </form>
          </div>
        </div>
      ) : (
        <div className="flex min-h-0 flex-1 flex-col">
          <h2 className="mb-2 text-sm font-semibold">
            {conversationQuery.data?.titre ?? (conversationQuery.isLoading ? "Chargement…" : "")}
          </h2>
          {erreurConversationOuverte && (
            <p role="alert" className="mb-2 text-sm text-destructive">
              {erreurConversationOuverte}
            </p>
          )}
          <div role="log" className="mb-3 flex min-h-0 flex-1 flex-col gap-2 overflow-y-auto">
            {messagesAffiches.map((message) =>
              message.role === "user" ? (
                <p
                  key={message.id}
                  className="self-end rounded-md bg-primary px-3 py-1.5 text-sm text-primary-foreground"
                >
                  {message.contenu}
                </p>
              ) : (
                <div key={message.id} className="max-w-[70%] self-start rounded-md bg-muted px-3 py-1.5 text-sm">
                  <ContenuMessageAssistant texte={message.contenu} />
                </div>
              )
            )}
            {envoiEnCours && (
              <>
                <BulleMessageEnvoye texte={envoiEnCours.message} />
                {envoiEnCours.phase === "attente" ? (
                  <output className="flex max-w-[70%] items-center gap-2 self-start rounded-md bg-muted px-3 py-1.5 text-sm text-muted-foreground">
                    <Loader2 className="size-3.5 animate-spin" aria-hidden="true" />
                    Réflexion…
                  </output>
                ) : (
                  <div className="max-w-[70%] self-start rounded-md bg-muted px-3 py-1.5 text-sm">
                    <TexteAnimeReponse
                      texte={envoiEnCours.reponse}
                      onTermine={() =>
                        setEnvoiEnCours((precedent) => (precedent ? { ...precedent, phase: "termine" } : precedent))
                      }
                    />
                  </div>
                )}
              </>
            )}
          </div>

          <form onSubmit={gererEnvoiMessage} className="flex flex-col gap-3">
            <ChampMessageAvecPieceJointe
              id="message"
              label="Message"
              valeur={champMessage}
              onChange={setChampMessage}
              fichier={fichierMessage}
              onFichierChange={setFichierMessage}
              disabled={envoiEnCours !== null}
            />
            {envoyerMessageMutation.data?.pieceJointeEchecAnalyse && (
              <output className="text-sm text-muted-foreground">
                L'IA n'a pas pu analyser la pièce jointe « {envoyerMessageMutation.data.pieceJointeNomFichier} ».
              </output>
            )}
            {erreurEnvoiMessage && (
              <p role="alert" className="text-sm text-destructive">
                {erreurEnvoiMessage}
              </p>
            )}
          </form>
        </div>
      )}
    </div>
  );
}
