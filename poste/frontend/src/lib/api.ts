// Petit client fetch partagé par les hooks de session/requête : même contrat
// HTTP qu'app.js (routes relatives, servies par le même poste FastAPI),
// simplement centralisé pour que chaque hook n'ait pas à répéter la gestion
// réseau/erreur.
export class ErreurApi extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ErreurApi";
    this.status = status;
  }
}

async function extraireMessageErreur(reponse: Response, messageParDefaut: string): Promise<string> {
  const detail = await reponse.json().catch(() => null);
  return detail && typeof detail.detail === "string" ? detail.detail : messageParDefaut;
}

export function messageErreur(erreur: unknown, messageParDefaut: string): string | null {
  if (!erreur) {
    return null;
  }
  return erreur instanceof ErreurApi ? erreur.message : messageParDefaut;
}

export async function appelApi<T>(
  chemin: string,
  options: RequestInit | undefined,
  messageErreurReseau: string,
  messageErreurParDefaut: string
): Promise<T> {
  let reponse: Response;
  try {
    reponse = await fetch(chemin, options);
  } catch {
    throw new ErreurApi(messageErreurReseau, 0);
  }

  if (!reponse.ok) {
    throw new ErreurApi(await extraireMessageErreur(reponse, messageErreurParDefaut), reponse.status);
  }

  if (reponse.status === 204) {
    return undefined as T;
  }

  return (await reponse.json()) as T;
}

interface EvenementFlux {
  nom: string;
  donnees: { libelle?: unknown; status?: unknown; detail?: unknown };
}

function lireEvenement(bloc: string): EvenementFlux | null {
  let nom = "";
  let donnees = "";
  for (const ligne of bloc.split("\n")) {
    if (ligne.startsWith("event: ")) {
      nom = ligne.slice("event: ".length);
    } else if (ligne.startsWith("data: ")) {
      donnees = ligne.slice("data: ".length);
    }
  }
  try {
    return { nom, donnees: JSON.parse(donnees) };
  } catch {
    // Événement à moitié reçu (VM coupée en plein flux) : ignoré, l'erreur
    // qui le suit dit pourquoi.
    return null;
  }
}

// Envoi d'un message (spec 1.4.4, ADR-0016) : un POST avec corps, donc
// fetch + ReadableStream plutôt qu'EventSource. Chaque `statut` passe à
// `onStatut` ; `fin` porte le JSON d'avant le flux ; `erreur` (pendant le
// tour) devient la même ErreurApi qu'un statut HTTP en erreur. Les refus
// d'avant le tour restent de vrais statuts HTTP.
export async function appelApiEnFlux<T>(
  chemin: string,
  options: RequestInit,
  onStatut: (libelle: string) => void,
  messageErreurReseau: string,
  messageErreurParDefaut: string
): Promise<T> {
  let reponse: Response;
  try {
    reponse = await fetch(chemin, options);
  } catch {
    throw new ErreurApi(messageErreurReseau, 0);
  }

  if (!reponse.ok || reponse.body === null) {
    throw new ErreurApi(await extraireMessageErreur(reponse, messageErreurParDefaut), reponse.status);
  }

  const lecteur = reponse.body.pipeThrough(new TextDecoderStream()).getReader();
  let tampon = "";
  for (;;) {
    let morceau: ReadableStreamReadResult<string>;
    try {
      morceau = await lecteur.read();
    } catch {
      throw new ErreurApi(messageErreurReseau, 0);
    }
    if (morceau.done) {
      // Flux fermé sans `fin` ni `erreur`.
      throw new ErreurApi(messageErreurParDefaut, 0);
    }
    tampon += morceau.value;
    let separateur = tampon.indexOf("\n\n");
    while (separateur !== -1) {
      const evenement = lireEvenement(tampon.slice(0, separateur));
      tampon = tampon.slice(separateur + 2);
      separateur = tampon.indexOf("\n\n");
      if (evenement?.nom === "statut" && typeof evenement.donnees.libelle === "string") {
        onStatut(evenement.donnees.libelle);
      } else if (evenement?.nom === "fin") {
        await lecteur.cancel();
        return evenement.donnees as T;
      } else if (evenement?.nom === "erreur") {
        await lecteur.cancel();
        const { detail, status } = evenement.donnees;
        throw new ErreurApi(
          typeof detail === "string" ? detail : messageErreurParDefaut,
          typeof status === "number" ? status : 0
        );
      }
    }
  }
}
