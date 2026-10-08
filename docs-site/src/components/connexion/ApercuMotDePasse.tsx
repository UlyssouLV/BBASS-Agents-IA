import type { ReactNode } from 'react';

import CadrePoste from '@site/src/components/cadre/CadrePoste';
import { EcranChangementMotDePasse } from '../../../../poste/frontend/src/screens/EcranChangementMotDePasse';

export default function ApercuMotDePasse(): ReactNode {
  return (
    <CadrePoste etroit>
      <EcranChangementMotDePasse
        changerMotDePasse={{ mutate: () => undefined, isPending: false, error: null } as never}
      />
    </CadrePoste>
  );
}
