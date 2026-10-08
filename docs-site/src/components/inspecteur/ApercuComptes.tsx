import type { ReactNode } from 'react';

import CadrePoste from '@site/src/components/cadre/CadrePoste';
import {
  CadrePageInspecteur,
  EnTeteNiveau,
  FilInspecteur,
  TableauComptesInspecteur,
  TitreInspecteur,
} from '../../../../poste/frontend/src/components/ChromeInspecteur';

export default function ApercuComptes(): ReactNode {
  return (
    <CadrePoste>
      <CadrePageInspecteur pleinEcran={false}>
        <TitreInspecteur />
        <FilInspecteur
          identifiant={null}
          titreConversation={null}
          onComptes={() => undefined}
          onCompte={() => undefined}
        />
        <EnTeteNiveau titre="Comptes" enCours={false} onRafraichir={() => undefined} />
        <TableauComptesInspecteur identifiants={['dupont', 'martin']} onChoisir={() => undefined} />
      </CadrePageInspecteur>
    </CadrePoste>
  );
}
