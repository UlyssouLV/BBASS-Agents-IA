import type { ReactNode } from 'react';

import CadrePoste from '@site/src/components/cadre/CadrePoste';
import { PuceCompte } from '../../../../poste/frontend/src/components/PuceCompte';

const compte = {
  prenom: 'Jeanne',
  nom: 'Dupont',
  poles: ['Urbanisme'],
  agence: 'Castries',
  est_admin: false,
};

export default function ApercuPuce(): ReactNode {
  return (
    <CadrePoste>
      <PuceCompte
        compte={compte}
        onOuvrirProfil={() => undefined}
        onOuvrirPanelAdministration={() => undefined}
      />
    </CadrePoste>
  );
}
