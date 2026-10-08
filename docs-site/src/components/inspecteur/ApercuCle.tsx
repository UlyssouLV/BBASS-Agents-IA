import type { ReactNode } from 'react';

import CadrePoste from '@site/src/components/cadre/CadrePoste';
import { EcranCleInspecteur } from '../../../../poste/frontend/src/screens/EcranCleInspecteur';

export default function ApercuCle(): ReactNode {
  return (
    <CadrePoste etroit>
      <EcranCleInspecteur erreur={null} onValider={() => undefined} focusAutomatique={false} />
    </CadrePoste>
  );
}
