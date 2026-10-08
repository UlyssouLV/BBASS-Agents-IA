import type { ReactNode } from 'react';

import CadrePoste from '@site/src/components/cadre/CadrePoste';
import { ErreurApi } from '../../../../poste/frontend/src/lib/api';
import { EcranConnexion } from '../../../../poste/frontend/src/screens/EcranConnexion';

type Props = {
  /** Message affiché sous le bouton, comme un échec de connexion. */
  message?: string;
};

export default function ApercuSaisie({ message }: Props): ReactNode {
  return (
    <CadrePoste etroit>
      <EcranConnexion
        connexion={
          {
            mutate: () => undefined,
            isPending: false,
            error: message ? new ErreurApi(message, 401) : null,
          } as never
        }
      />
    </CadrePoste>
  );
}
