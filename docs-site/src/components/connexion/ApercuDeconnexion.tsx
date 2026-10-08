import type { ReactNode } from 'react';

import CadrePoste from '@site/src/components/cadre/CadrePoste';
import { EnteteProfil } from '../../../../poste/frontend/src/components/EnteteProfil';
import { EnteteComptesAdmin, LigneCompteAdmin } from '../../../../poste/frontend/src/components/LigneCompteAdmin';
import { Table, TableBody } from '../../../../poste/frontend/src/components/ui/table';

export default function ApercuDeconnexion(): ReactNode {
  return (
    <CadrePoste>
      <EnteteProfil
        onRetour={() => undefined}
        onDeconnexion={() => undefined}
        deconnexionEnCours={false}
      />
    </CadrePoste>
  );
}

const compte = {
  identifiant: 'j.dupont',
  prenom: 'Jeanne',
  nom: 'Dupont',
  agence: 'Castries',
  poles: ['Urbanisme'],
  est_admin: false,
  email: null,
};

export function ApercuDeconnexionForcee(): ReactNode {
  return (
    <CadrePoste>
      <Table>
        <EnteteComptesAdmin />
        <TableBody>
          <LigneCompteAdmin
            compte={compte}
            reinitialisationEnCours={false}
            deconnexionEnCours={false}
            onModifier={() => undefined}
            onReinitialiser={() => undefined}
            onForcerDeconnexion={() => undefined}
            onChangerStatut={() => undefined}
            onSupprimer={() => undefined}
          />
        </TableBody>
      </Table>
    </CadrePoste>
  );
}
