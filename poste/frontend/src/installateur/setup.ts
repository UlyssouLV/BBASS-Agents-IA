import { Channel, invoke } from "@tauri-apps/api/core";

// Commandes du Setup (lanceur/src/installateur.rs).

export interface Informations {
  version: string;
  emplacement: string;
  hote: string;
  port: number;
}

export interface EtatServeur {
  joignable: boolean;
  version: string | null;
}

export interface Options {
  hote: string;
  port: number;
  demarrageWindows: boolean;
  raccourciBureau: boolean;
}

export interface Progression {
  etape: string;
  fraction: number;
}

export function lireInformations(): Promise<Informations> {
  return invoke("informations");
}

export function testerServeur(hote: string, port: number): Promise<EtatServeur> {
  return invoke("tester_serveur", { hote, port });
}

// Rejette avec le message en français du Setup.
export function installer(options: Options, surProgression: (progression: Progression) => void): Promise<void> {
  const progression = new Channel<Progression>();
  progression.onmessage = surProgression;
  return invoke("installer", { options, progression });
}

export function lancerBbass(): Promise<void> {
  return invoke("lancer_bbass");
}
