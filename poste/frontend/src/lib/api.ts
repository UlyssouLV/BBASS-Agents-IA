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
