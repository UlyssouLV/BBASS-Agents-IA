import type { ReactNode } from 'react';

import CadrePoste from '@site/src/components/cadre/CadrePoste';
import {
  BlocTexte,
  CoquilleCarteEchange,
  MessageRole,
  SectionEchange,
} from '../../../../poste/frontend/src/components/CoquilleCarteEchange';

export interface CarteApercuProps {
  libelle: string;
  origine: 'mistral' | 'local';
  statut?: 'succes' | 'echec';
  date?: string;
  modele?: string;
  /** Carte déjà dépliée à l’affichage (ex. exemple principal d’une fiche). */
  ouvertParDefaut?: boolean;
  children?: ReactNode;
}

const _DATE_EXEMPLE = '2026-10-06T14:02:00';

export default function CarteApercu({
  libelle,
  origine,
  statut = 'succes',
  date = _DATE_EXEMPLE,
  modele,
  ouvertParDefaut = false,
  children,
}: CarteApercuProps): ReactNode {
  const local = origine === 'local';
  return (
    <CadrePoste>
      <CoquilleCarteEchange
        libelle={libelle}
        local={local}
        enEchec={statut === 'echec'}
        dateIso={date}
        ouvertParDefaut={ouvertParDefaut}
      >
        {!local && modele ? <p className="text-xs text-muted-foreground">Modèle : {modele}</p> : null}
        {children}
      </CoquilleCarteEchange>
    </CadrePoste>
  );
}

export function SectionApercu({
  titre,
  children,
}: {
  titre: string;
  children: ReactNode;
}): ReactNode {
  return <SectionEchange titre={titre}>{children}</SectionEchange>;
}

export function MessageApercu({ role, children }: { role: string; children: ReactNode }): ReactNode {
  return (
    <CadrePoste>
      <MessageRole role={role}>
        <p className="whitespace-pre-wrap break-words">{children}</p>
      </MessageRole>
    </CadrePoste>
  );
}

export function JsonApercu({ children }: { children: string }): ReactNode {
  return <BlocTexte>{children}</BlocTexte>;
}
