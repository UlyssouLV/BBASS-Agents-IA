import type {ReactNode} from 'react';

import styles from './schemas.module.css';

type Variante = 'appel' | 'demarrage' | 'chiffrement';

const ETAPES: Record<Variante, {ou: string; fait: string}[]> = {
  appel: [
    {ou: 'Interface', fait: 'Question du collaborateur, ex. « Qui sont les intervenants de l’affaire 2024-123 ? »'},
    {ou: 'Modèle', fait: 'Décide d’appeler chercher_affaires_moduleo ou chercher_contacts_moduleo, avec des noms'},
    {ou: 'VM centrale', fait: 'Statut « Consultation Moduléo », puis noms → ids'},
    {ou: 'Moduléo', fait: 'Lectures GET seulement, avec la clé d’API et le code de sécurité'},
    {ou: 'VM centrale', fait: 'Ids → noms, une Fiche Moduléo par résultat, enregistrée dans la Conversation'},
    {ou: 'Modèle', fait: 'Répond à partir des fiches'},
    {ou: 'Interface', fait: 'Réponse avec chiffres gardés et « Sources : Moduléo, affaire 2024-123 »'},
  ],
  demarrage: [
    {ou: 'VM centrale', fait: 'Lit MODULEO_URL, les deux secrets chiffrés et VM_CLE_MAITRE_FICHIER dans .env'},
    {ou: 'Fichier', fait: 'Lit la clé maître à ce chemin'},
    {ou: 'VM centrale', fait: 'Déchiffre la clé d’API et le code de sécurité, en mémoire seulement'},
    {ou: 'Modèle', fait: 'Les deux outils Moduléo sont proposés à chaque appel de chat'},
  ],
  chiffrement: [
    {ou: 'Terminal', fait: 'python scripts/chiffrer_secret.py MODULEO_API_KEY_CHIFFREE'},
    {ou: 'Fichier', fait: 'Crée la clé maître si elle n’existe pas encore (jamais ne l’écrase)'},
    {ou: 'Terminal', fait: 'Demande le secret, sans l’afficher'},
    {ou: 'Terminal', fait: 'Imprime MODULEO_API_KEY_CHIFFREE=gAAAAA…, à coller dans .env'},
  ],
};

// Enchaînement d’un branchement Moduléo, même présentation que les
// schémas de Connexion (où, ce qui s’y fait).
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
