/**
 * Termes du glossaire (docs/glossaire.md), du plus long au plus court.
 */
const TERMES_GLOSSAIRE = [
  {
    formes: ["Clé d'administration VM", "Clé d’administration VM"],
    slug: 'cle-d-administration-vm',
    resume: 'Secret partagé qui autorise les actions sensibles de la VM centrale, dont le Mode développeur.',
  },
  {
    formes: ['Mémoire de la conversation'],
    slug: 'memoire-de-la-conversation',
    resume: 'Liste de ce qui a été partagé dans une Conversation, recalculée à chaque appel de chat.',
  },
  {
    formes: ['Compte administrateur', 'comptes administrateur'],
    slug: 'compte-administrateur',
    resume: 'Compte avec le droit global de gérer les autres comptes. Distinct de la Clé d’administration VM.',
  },
  {
    formes: ['Profil de travail'],
    slug: 'profil-de-travail',
    resume: 'Résumé synthétique par compte de sa façon de travailler, distinct de l’historique d’une conversation.',
  },
  {
    formes: ['Étape de traitement', 'Etape de traitement'],
    slug: 'etape-de-traitement',
    resume: 'Traitement imposé par la VM à chaque tour, sans que le modèle le demande.',
  },
  {
    formes: ["Appel d'extraction", "Appel d’extraction"],
    slug: 'appel-d-extraction',
    resume: 'Appel au modèle interne à une Recherche web, isolé du contexte de la Conversation.',
  },
  {
    formes: ['Mode développeur'],
    slug: 'mode-developpeur',
    resume: 'Accès technique au poste, débloqué par la Clé d’administration VM ; ouvre l’inspecteur.',
  },
  {
    formes: ['Question couverte', 'Questions couvertes'],
    slug: 'question-couverte',
    resume: 'Question à laquelle une pièce jointe ou une page lue répond, avec sa source.',
  },
  {
    formes: ['Fiche de modèle', 'Fiche de modele'],
    slug: 'fiche-de-modele',
    resume: 'Tout ce qui dépend d’un modèle (fenêtre, tokenizer, tarifs), regroupé sur la VM.',
  },
  {
    formes: ['Jauge de contexte'],
    slug: 'jauge-de-contexte',
    resume: 'Cercle sous le champ de saisie : tokens du dernier envoi sur la fenêtre du modèle.',
  },
  {
    formes: ['Recherche web'],
    slug: 'recherche-web',
    resume: 'Outil rechercher_web : moteur auto-hébergé, pages lues, puis appel d’extraction.',
  },
  {
    formes: ['Relais Mistral'],
    slug: 'relais-mistral',
    resume: 'Service de la VM qui détient la clé API du fournisseur et relaie les appels des postes.',
  },
  {
    formes: ['Pièce jointe', 'Pièces jointes', 'pièce jointe', 'pièces jointes'],
    slug: 'piece-jointe',
    resume: 'Fichier joint à un message, stocké sur la VM, jamais chez le fournisseur.',
  },
  {
    formes: ['VM centrale'],
    slug: 'vm-centrale',
    resume: 'Machine à Castries : base, auth, relais vers le fournisseur de modèle.',
  },
  {
    formes: ['Consommation'],
    slug: 'consommation',
    resume: 'Enregistrement d’un appel au modèle (tokens, coût, date) pour un compte.',
  },
  {
    formes: ['Conversation', 'Conversations'],
    slug: 'conversation',
    resume: 'Fil d’échanges avec l’IA, privé à son compte, persisté par la VM centrale.',
  },
  {
    formes: ['Garde-fou', 'Garde-fous', 'garde-fou', 'garde-fous'],
    slug: 'garde-fou',
    resume: 'Correction appliquée par la VM à la sortie du modèle malgré sa consigne.',
  },
  {
    formes: ['Satellite', 'Satellites'],
    slug: 'satellite',
    resume: 'Agence autre que Castries. Hors périmètre de déploiement de la V1.',
  },
  {
    formes: ['Échange', 'Échanges'],
    slug: 'echange',
    resume: 'Étape technique capturée pour le Mode développeur (appel modèle ou travail local).',
  },
  {
    formes: ['Session'],
    slug: 'session',
    resume: 'État de connexion d’un compte sur un poste, persisté via Windows et la VM.',
  },
  {
    formes: ['Agence', 'Agences'],
    slug: 'agence',
    resume: 'Site physique du cabinet. Castries est la maison mère.',
  },
  {
    formes: ['Compte', 'Comptes'],
    slug: 'compte',
    resume: 'Identité de connexion d’un collaborateur, rattachée à une agence et à des pôles.',
  },
  {
    formes: ['Poste'],
    slug: 'poste',
    resume: 'Machine du collaborateur : backend Python et interface web locaux.',
  },
  {
    formes: ['Outil', 'Outils'],
    slug: 'outil',
    resume: 'Capacité que le modèle décide d’appeler ; la VM l’exécute et lui renvoie le résultat.',
  },
  {
    formes: ['Agent', 'Agents'],
    slug: 'agent',
    resume: 'Système IA destiné à un pôle. Non construit en V1.',
  },
  {
    formes: ['Pôle', 'Pôles'],
    slug: 'pole',
    resume: 'Un des six domaines métiers du cabinet (Administration, Foncier, etc.).',
  },
];

module.exports = {TERMES_GLOSSAIRE};
