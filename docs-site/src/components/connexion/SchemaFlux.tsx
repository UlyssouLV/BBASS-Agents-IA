import type {ReactNode} from 'react';

import styles from './apercus.module.css';

type Variante = 'connexion' | 'restauration' | 'mot-de-passe' | 'deconnexion';

const ETAPES: Record<Variante, {ou: string; fait: string}[]> = {
  connexion: [
    {ou: 'Interface', fait: 'Identifiant et mot de passe'},
    {ou: 'Poste', fait: 'POST /connexion'},
    {ou: 'VM centrale', fait: 'POST /auth — le hash du compte est comparé au mot de passe'},
    {ou: 'Base', fait: 'Un jeton est enregistré pour ce compte'},
    {ou: 'Poste', fait: 'La session est gardée en mémoire et dans le gestionnaire Windows'},
    {ou: 'Interface', fait: 'Chat, ou changement de mot de passe si le compte doit encore le choisir'},
  ],
  restauration: [
    {ou: 'Poste', fait: 'Lecture du jeton déjà stocké, au lancement'},
    {ou: 'VM centrale', fait: 'GET /auth/verifier'},
    {ou: 'Interface', fait: 'Chat si le jeton est encore valide, sinon écran de connexion'},
  ],
  'mot-de-passe': [
    {ou: 'Interface', fait: 'Nouveau mot de passe, saisi deux fois'},
    {ou: 'Poste', fait: 'POST /mot-de-passe'},
    {ou: 'VM centrale', fait: 'POST /auth/mot-de-passe — nouveau hash, obligation levée'},
    {ou: 'Interface', fait: 'Accès au chat'},
  ],
  deconnexion: [
    {ou: 'Interface', fait: 'Profil, puis « Se déconnecter »'},
    {ou: 'Poste', fait: 'La session locale est effacée'},
    {ou: 'VM centrale', fait: 'DELETE /auth/jeton — ce jeton est retiré'},
    {ou: 'Interface', fait: 'Retour à l’écran de connexion'},
  ],
};

// Enchaînement poste → VM, même découpage que la vue système
// (interface, backend poste, VM centrale, base).
export default function SchemaFlux({variante}: {variante: Variante}): ReactNode {
  return (
    <div className={styles.cadre}>
      <ol className={styles.flux}>
        {ETAPES[variante].map((etape) => (
          <li key={`${etape.ou}-${etape.fait}`} className={styles.etape}>
            <span className={styles.ou}>{etape.ou}</span>
            <span>{etape.fait}</span>
          </li>
        ))}
      </ol>
    </div>
  );
}
