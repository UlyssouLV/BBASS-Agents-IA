import type { ReactNode } from 'react';

import CadrePoste from '@site/src/components/cadre/CadrePoste';
import {
  CadrePageInspecteur,
  EnTeteNiveau,
  FilInspecteur,
  TableauConversationsInspecteur,
  TitreInspecteur,
} from '../../../../poste/frontend/src/components/ChromeInspecteur';

export default function ApercuConversations(): ReactNode {
  return (
    <CadrePoste>
      <CadrePageInspecteur pleinEcran={false}>
        <TitreInspecteur />
        <FilInspecteur
          identifiant="dupont"
          titreConversation={null}
          onComptes={() => undefined}
          onCompte={() => undefined}
        />
        <EnTeteNiveau titre="Conversations de dupont" enCours={false} onRafraichir={() => undefined} />
        <TableauConversationsInspecteur
          lignes={[
            {
              id: 1,
              titre: 'Recherche PLU Castries',
              dateCreation: '2026-10-06T09:12:00',
              dateActivite: '2026-10-06T14:02:00',
            },
          ]}
          onChoisir={() => undefined}
        />
      </CadrePageInspecteur>
    </CadrePoste>
  );
}
