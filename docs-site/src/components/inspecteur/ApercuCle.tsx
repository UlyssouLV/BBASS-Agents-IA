import type {ReactNode} from 'react';

import styles from './apercus.module.css';

// Reprend l’écran EcranCleInspecteur (PageInspecteur.tsx) : même titre, même
// consigne, même libellé de champ. La saisie n’est pas branchée : c’est un aperçu.
export default function ApercuCle(): ReactNode {
  return (
    <div className={styles.cadre}>
      <h2 className={styles.titre}>Inspecteur des échanges avec le modèle</h2>
      <p className={styles.aide}>
        La Clé d&apos;administration VM est requise pour ouvrir le mode développeur.
      </p>
      <form
        onSubmit={(evenement) => evenement.preventDefault()}
        className={styles.champ}
        style={{gap: '1rem'}}>
        <label className={styles.champ}>
          Clé d&apos;administration VM
          <input type="password" value="••••••••" readOnly aria-label="Clé d'administration VM" />
        </label>
        <button type="button" className={styles.bouton}>
          Ouvrir l&apos;inspecteur
        </button>
      </form>
    </div>
  );
}
