const ecranConnexion = document.getElementById("ecran-connexion");
const ecranChangementMotDePasse = document.getElementById("ecran-changement-mot-de-passe");
const ecranCompte = document.getElementById("ecran-compte");
const formulaireConnexion = document.getElementById("formulaire-connexion");
const erreurConnexion = document.getElementById("erreur-connexion");
const formulaireChangementMotDePasse = document.getElementById("formulaire-changement-mot-de-passe");
const erreurChangementMotDePasse = document.getElementById("erreur-changement-mot-de-passe");
const nouveauMotDePasseChamp = document.getElementById("nouveau-mot-de-passe");
const confirmationMotDePasseChamp = document.getElementById("confirmation-mot-de-passe");
const identifiantConnecte = document.getElementById("identifiant-connecte");
const poleAgenceConnecte = document.getElementById("pole-agence-connecte");
const boutonDeconnexion = document.getElementById("bouton-deconnexion");
const avertissementSession = document.getElementById("avertissement-session");
const messages = document.getElementById("messages");
const chatChargement = document.getElementById("chat-chargement");
const chatErreur = document.getElementById("chat-erreur");
const formulaireChat = document.getElementById("formulaire-chat");
const champMessage = document.getElementById("message");

const conversationsErreur = document.getElementById("conversations-erreur");
const listeConversations = document.getElementById("liste-conversations");
const boutonNouvelleConversation = document.getElementById("bouton-nouvelle-conversation");
const nouvelleConversationZone = document.getElementById("nouvelle-conversation");
const formulaireNouvelleConversation = document.getElementById("formulaire-nouvelle-conversation");
const nouveauMessageConversation = document.getElementById("nouveau-message-conversation");
const nouvelleConversationErreur = document.getElementById("nouvelle-conversation-erreur");
const conversationOuverte = document.getElementById("conversation-ouverte");
const conversationTitre = document.getElementById("conversation-titre");

const ongletBoutonChat = document.getElementById("onglet-bouton-chat");
const ongletBoutonComptes = document.getElementById("onglet-bouton-comptes");
const ongletChat = document.getElementById("onglet-chat");
const ongletComptes = document.getElementById("onglet-comptes");
const comptesErreur = document.getElementById("comptes-erreur");
const corpsTableauComptes = document.getElementById("corps-tableau-comptes");
const formulaireCreationCompte = document.getElementById("formulaire-creation-compte");
const creationErreur = document.getElementById("creation-erreur");
const compteCree = document.getElementById("compte-cree");
const compteCreeMotDePasse = document.getElementById("compte-cree-mot-de-passe");
const motDePasseReinitialise = document.getElementById("mot-de-passe-reinitialise");
const motDePasseReinitialiseIdentifiant = document.getElementById("mot-de-passe-reinitialise-identifiant");
const motDePasseReinitialiseValeur = document.getElementById("mot-de-passe-reinitialise-valeur");
const deconnexionForceeConfirmation = document.getElementById("deconnexion-forcee-confirmation");
const deconnexionForceeIdentifiant = document.getElementById("deconnexion-forcee-identifiant");
const modificationTitre = document.getElementById("modification-titre");
const modificationIdentifiant = document.getElementById("modification-identifiant");
const formulaireModificationCompte = document.getElementById("formulaire-modification-compte");
const modificationErreur = document.getElementById("modification-erreur");
const modificationAnnuler = document.getElementById("modification-annuler");
const statutAdminTitre = document.getElementById("statut-admin-titre");
const statutAdminAction = document.getElementById("statut-admin-action");
const statutAdminIdentifiant = document.getElementById("statut-admin-identifiant");
const formulaireStatutAdmin = document.getElementById("formulaire-statut-admin");
const statutAdminCle = document.getElementById("statut-admin-cle");
const statutAdminAnnuler = document.getElementById("statut-admin-annuler");
const statutAdminErreur = document.getElementById("statut-admin-erreur");
const statutAdminConfirmation = document.getElementById("statut-admin-confirmation");
const statutAdminConfirmationIdentifiant = document.getElementById("statut-admin-confirmation-identifiant");
const statutAdminConfirmationStatut = document.getElementById("statut-admin-confirmation-statut");
const suppressionTitre = document.getElementById("suppression-titre");
const suppressionIdentifiant = document.getElementById("suppression-identifiant");
const formulaireSuppressionCompte = document.getElementById("formulaire-suppression-compte");
const suppressionCle = document.getElementById("suppression-cle");
const suppressionAnnuler = document.getElementById("suppression-annuler");
const suppressionErreur = document.getElementById("suppression-erreur");
const suppressionConfirmation = document.getElementById("suppression-confirmation");
const suppressionConfirmationIdentifiant = document.getElementById("suppression-confirmation-identifiant");

let comptesActuels = [];
let identifiantEnCoursDeModification = null;
let identifiantEnCoursDeChangementStatutAdmin = null;
let estAdminCibleEnCours = null;
let identifiantEnCoursDeSuppression = null;
let conversationOuverteId = null;

async function afficherOngletChat() {
  ongletChat.hidden = false;
  ongletComptes.hidden = true;
  afficherNouvelleConversation();
  await chargerConversations();
}

async function afficherOngletComptes() {
  ongletChat.hidden = true;
  ongletComptes.hidden = false;
  await chargerComptes();
}

function afficherEcranCompte(compte) {
  // Un compte qui doit encore changer son mot de passe (création ou
  // réinitialisation par un administrateur, voir docs/specs/v1.1-gestion-
  // comptes-admin.md) ne doit jamais atteindre l'écran de chat, ni à la
  // connexion ni à la restauration de session : l'écran de changement de
  // mot de passe obligatoire prend sa place tant que ce n'est pas fait.
  if (compte.doit_changer_mot_de_passe) {
    afficherEcranChangementMotDePasse();
    return;
  }

  identifiantConnecte.textContent = `${compte.prenom} ${compte.nom} (${compte.identifiant})`;
  poleAgenceConnecte.textContent = [compte.poles.join(", "), compte.agence].filter(Boolean).join(" — ");
  if (compte.avertissement) {
    avertissementSession.textContent = compte.avertissement;
    avertissementSession.hidden = false;
  } else {
    avertissementSession.hidden = true;
  }
  // L'onglet Comptes n'apparaît que pour une session administrateur (voir
  // docs/specs/v1.1-gestion-comptes-admin.md) : est_admin n'est jamais mis
  // en cache au-delà de cette vérification côté poste non plus.
  ongletBoutonComptes.hidden = !compte.est_admin;
  afficherOngletChat();
  ecranConnexion.hidden = true;
  ecranChangementMotDePasse.hidden = true;
  ecranCompte.hidden = false;
}

function afficherEcranChangementMotDePasse() {
  ecranConnexion.hidden = true;
  ecranCompte.hidden = true;
  erreurChangementMotDePasse.hidden = true;
  ecranChangementMotDePasse.hidden = false;
}

function afficherEcranConnexion() {
  ecranConnexion.hidden = false;
  ecranChangementMotDePasse.hidden = true;
  ecranCompte.hidden = true;
  erreurConnexion.hidden = true;
  messages.replaceChildren();
  chatErreur.hidden = true;
  ongletBoutonComptes.hidden = true;
  conversationOuverteId = null;
}

function ajouterMessage(auteur, texte) {
  const paragraphe = document.createElement("p");
  paragraphe.className = auteur === "collaborateur" ? "message-collaborateur" : "message-reponse";
  paragraphe.textContent = texte;
  messages.append(paragraphe);
}

async function verifierSessionActive() {
  const reponse = await fetch("/compte");
  if (reponse.ok) {
    const compte = await reponse.json();
    afficherEcranCompte(compte);
  }
}

formulaireConnexion.addEventListener("submit", async (evenement) => {
  evenement.preventDefault();
  erreurConnexion.hidden = true;

  const identifiant = document.getElementById("identifiant").value;
  const motDePasse = document.getElementById("mot-de-passe").value;

  let reponse;
  try {
    reponse = await fetch("/connexion", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ identifiant, mot_de_passe: motDePasse }),
    });
  } catch {
    erreurConnexion.textContent = "Impossible de joindre le service de connexion. Réessayez plus tard.";
    erreurConnexion.hidden = false;
    return;
  }

  if (!reponse.ok) {
    const detail = await reponse.json().catch(() => null);
    erreurConnexion.textContent =
      detail && detail.detail ? detail.detail : "La connexion a échoué. Réessayez plus tard.";
    erreurConnexion.hidden = false;
    return;
  }

  const compte = await reponse.json();
  afficherEcranCompte(compte);
});

formulaireChangementMotDePasse.addEventListener("submit", async (evenement) => {
  evenement.preventDefault();
  erreurChangementMotDePasse.hidden = true;

  const nouveauMotDePasse = nouveauMotDePasseChamp.value;
  const confirmation = confirmationMotDePasseChamp.value;

  if (nouveauMotDePasse !== confirmation) {
    erreurChangementMotDePasse.textContent = "Les mots de passe saisis ne correspondent pas.";
    erreurChangementMotDePasse.hidden = false;
    return;
  }

  let reponse;
  try {
    reponse = await fetch("/mot-de-passe", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ nouveau_mot_de_passe: nouveauMotDePasse }),
    });
  } catch {
    erreurChangementMotDePasse.textContent =
      "Impossible de joindre le service de connexion. Réessayez plus tard.";
    erreurChangementMotDePasse.hidden = false;
    return;
  }

  if (reponse.status === 401) {
    afficherEcranConnexion();
    return;
  }

  if (!reponse.ok) {
    const detail = await reponse.json().catch(() => null);
    erreurChangementMotDePasse.textContent =
      detail && detail.detail ? detail.detail : "Le changement de mot de passe a échoué. Réessayez plus tard.";
    erreurChangementMotDePasse.hidden = false;
    return;
  }

  formulaireChangementMotDePasse.reset();
  const compte = await reponse.json();
  afficherEcranCompte(compte);
});

boutonDeconnexion.addEventListener("click", async () => {
  await fetch("/deconnexion", { method: "POST" });
  afficherEcranConnexion();
});

formulaireChat.addEventListener("submit", async (evenement) => {
  evenement.preventDefault();
  chatErreur.hidden = true;

  const message = champMessage.value;
  if (!message.trim() || conversationOuverteId === null) {
    return;
  }

  ajouterMessage("collaborateur", message);
  champMessage.value = "";
  champMessage.disabled = true;
  chatChargement.hidden = false;

  try {
    let reponse;
    try {
      reponse = await fetch(`/conversations/${conversationOuverteId}/messages`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message }),
      });
    } catch {
      chatErreur.textContent = "Impossible de joindre le service de conversations. Réessayez plus tard.";
      chatErreur.hidden = false;
      return;
    }

    if (reponse.status === 401) {
      afficherEcranConnexion();
      return;
    }

    if (!reponse.ok) {
      const detail = await reponse.json().catch(() => null);
      chatErreur.textContent =
        detail && detail.detail ? detail.detail : "L'envoi du message a échoué. Réessayez plus tard.";
      chatErreur.hidden = false;
      return;
    }

    const corps = await reponse.json();
    ajouterMessage("reponse", corps.reponse);
  } finally {
    chatChargement.hidden = true;
    // Un 401 a déjà basculé vers l'écran de connexion (champMessage n'y est
    // plus visible) : ne pas le réactiver/focaliser dans ce cas.
    if (!ecranCompte.hidden) {
      champMessage.disabled = false;
      champMessage.focus();
    }
  }
});

function afficherNouvelleConversation() {
  conversationOuverteId = null;
  conversationOuverte.hidden = true;
  nouvelleConversationZone.hidden = false;
  nouvelleConversationErreur.hidden = true;
}

function afficherConversationOuverte(id, titre, messagesConversation) {
  conversationOuverteId = id;
  nouvelleConversationZone.hidden = true;
  conversationOuverte.hidden = false;
  conversationTitre.textContent = titre;
  chatErreur.hidden = true;
  messages.replaceChildren();
  for (const message of messagesConversation) {
    ajouterMessage(message.role === "user" ? "collaborateur" : "reponse", message.contenu);
  }
}

function ligneConversation(conversation) {
  const ligne = document.createElement("li");

  const boutonOuvrir = document.createElement("button");
  boutonOuvrir.type = "button";
  boutonOuvrir.textContent = conversation.titre;
  boutonOuvrir.addEventListener("click", () => ouvrirConversation(conversation.id));
  ligne.append(boutonOuvrir);

  const boutonRenommer = document.createElement("button");
  boutonRenommer.type = "button";
  boutonRenommer.textContent = "Renommer";
  boutonRenommer.addEventListener("click", () => renommerConversation(conversation.id, conversation.titre));
  ligne.append(boutonRenommer);

  const boutonSupprimer = document.createElement("button");
  boutonSupprimer.type = "button";
  boutonSupprimer.textContent = "Supprimer";
  boutonSupprimer.addEventListener("click", () => supprimerConversation(conversation.id));
  ligne.append(boutonSupprimer);

  return ligne;
}

async function chargerConversations() {
  conversationsErreur.hidden = true;

  let reponse;
  try {
    reponse = await fetch("/conversations");
  } catch {
    conversationsErreur.textContent = "Impossible de joindre le service de conversations. Réessayez plus tard.";
    conversationsErreur.hidden = false;
    return;
  }

  if (reponse.status === 401) {
    afficherEcranConnexion();
    return;
  }

  if (!reponse.ok) {
    const detail = await reponse.json().catch(() => null);
    conversationsErreur.textContent =
      detail && detail.detail ? detail.detail : "Le chargement des conversations a échoué. Réessayez plus tard.";
    conversationsErreur.hidden = false;
    return;
  }

  const conversations = await reponse.json();
  listeConversations.replaceChildren(...conversations.map(ligneConversation));
}

async function ouvrirConversation(id) {
  conversationsErreur.hidden = true;

  let reponse;
  try {
    reponse = await fetch(`/conversations/${id}`);
  } catch {
    conversationsErreur.textContent = "Impossible de joindre le service de conversations. Réessayez plus tard.";
    conversationsErreur.hidden = false;
    return;
  }

  if (reponse.status === 401) {
    afficherEcranConnexion();
    return;
  }

  if (!reponse.ok) {
    const detail = await reponse.json().catch(() => null);
    conversationsErreur.textContent =
      detail && detail.detail ? detail.detail : "L'ouverture de la conversation a échoué. Réessayez plus tard.";
    conversationsErreur.hidden = false;
    return;
  }

  const conversation = await reponse.json();
  afficherConversationOuverte(conversation.id, conversation.titre, conversation.messages);
}

boutonNouvelleConversation.addEventListener("click", afficherNouvelleConversation);

formulaireNouvelleConversation.addEventListener("submit", async (evenement) => {
  evenement.preventDefault();
  nouvelleConversationErreur.hidden = true;

  const message = nouveauMessageConversation.value;
  if (!message.trim()) {
    return;
  }

  let reponse;
  try {
    reponse = await fetch("/conversations", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message }),
    });
  } catch {
    nouvelleConversationErreur.textContent =
      "Impossible de joindre le service de conversations. Réessayez plus tard.";
    nouvelleConversationErreur.hidden = false;
    return;
  }

  if (reponse.status === 401) {
    afficherEcranConnexion();
    return;
  }

  if (!reponse.ok) {
    const detail = await reponse.json().catch(() => null);
    nouvelleConversationErreur.textContent =
      detail && detail.detail ? detail.detail : "La création de la conversation a échoué. Réessayez plus tard.";
    nouvelleConversationErreur.hidden = false;
    return;
  }

  const corps = await reponse.json();
  formulaireNouvelleConversation.reset();
  afficherConversationOuverte(corps.conversation.id, corps.conversation.titre, [
    { role: "user", contenu: message },
    { role: "assistant", contenu: corps.reponse },
  ]);
  await chargerConversations();
});

async function renommerConversation(id, titreActuel) {
  const nouveauTitre = window.prompt("Nouveau titre de la conversation :", titreActuel);
  if (!nouveauTitre || !nouveauTitre.trim() || nouveauTitre === titreActuel) {
    return;
  }

  conversationsErreur.hidden = true;

  let reponse;
  try {
    reponse = await fetch(`/conversations/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ titre: nouveauTitre }),
    });
  } catch {
    conversationsErreur.textContent = "Impossible de joindre le service de conversations. Réessayez plus tard.";
    conversationsErreur.hidden = false;
    return;
  }

  if (reponse.status === 401) {
    afficherEcranConnexion();
    return;
  }

  if (!reponse.ok) {
    const detail = await reponse.json().catch(() => null);
    conversationsErreur.textContent =
      detail && detail.detail ? detail.detail : "Le renommage de la conversation a échoué. Réessayez plus tard.";
    conversationsErreur.hidden = false;
    return;
  }

  const conversation = await reponse.json();
  if (conversationOuverteId === id) {
    conversationTitre.textContent = conversation.titre;
  }
  await chargerConversations();
}

async function supprimerConversation(id) {
  if (!window.confirm("Supprimer définitivement cette conversation ?")) {
    return;
  }

  conversationsErreur.hidden = true;

  let reponse;
  try {
    reponse = await fetch(`/conversations/${id}`, { method: "DELETE" });
  } catch {
    conversationsErreur.textContent = "Impossible de joindre le service de conversations. Réessayez plus tard.";
    conversationsErreur.hidden = false;
    return;
  }

  if (reponse.status === 401) {
    afficherEcranConnexion();
    return;
  }

  if (!reponse.ok) {
    const detail = await reponse.json().catch(() => null);
    conversationsErreur.textContent =
      detail && detail.detail ? detail.detail : "La suppression de la conversation a échoué. Réessayez plus tard.";
    conversationsErreur.hidden = false;
    return;
  }

  if (conversationOuverteId === id) {
    afficherNouvelleConversation();
  }
  await chargerConversations();
}

ongletBoutonChat.addEventListener("click", afficherOngletChat);
ongletBoutonComptes.addEventListener("click", afficherOngletComptes);

function ligneCompte(compte) {
  const ligne = document.createElement("tr");
  for (const valeur of [compte.identifiant, compte.prenom, compte.nom, compte.agence, compte.poles.join(", "), compte.email || ""]) {
    const cellule = document.createElement("td");
    cellule.textContent = valeur;
    ligne.append(cellule);
  }

  const celluleActions = document.createElement("td");
  const boutonModifier = document.createElement("button");
  boutonModifier.type = "button";
  boutonModifier.textContent = "Modifier";
  boutonModifier.dataset.identifiant = compte.identifiant;
  boutonModifier.addEventListener("click", () => ouvrirModificationCompte(compte.identifiant));
  celluleActions.append(boutonModifier);

  const boutonReinitialiser = document.createElement("button");
  boutonReinitialiser.type = "button";
  boutonReinitialiser.textContent = "Réinitialiser le mot de passe";
  boutonReinitialiser.dataset.identifiant = compte.identifiant;
  boutonReinitialiser.addEventListener("click", () => reinitialiserMotDePasse(compte.identifiant));
  celluleActions.append(boutonReinitialiser);

  const boutonDeconnecter = document.createElement("button");
  boutonDeconnecter.type = "button";
  boutonDeconnecter.textContent = "Forcer la déconnexion";
  boutonDeconnecter.dataset.identifiant = compte.identifiant;
  boutonDeconnecter.addEventListener("click", () => forcerLaDeconnexion(compte.identifiant));
  celluleActions.append(boutonDeconnecter);

  const boutonStatutAdmin = document.createElement("button");
  boutonStatutAdmin.type = "button";
  boutonStatutAdmin.textContent = compte.est_admin ? "Rétrograder" : "Promouvoir administrateur";
  boutonStatutAdmin.dataset.identifiant = compte.identifiant;
  boutonStatutAdmin.addEventListener("click", () =>
    ouvrirChangementStatutAdmin(compte.identifiant, !compte.est_admin)
  );
  celluleActions.append(boutonStatutAdmin);

  const boutonSupprimer = document.createElement("button");
  boutonSupprimer.type = "button";
  boutonSupprimer.textContent = "Supprimer";
  boutonSupprimer.dataset.identifiant = compte.identifiant;
  boutonSupprimer.addEventListener("click", () => ouvrirSuppressionCompte(compte.identifiant));
  celluleActions.append(boutonSupprimer);

  ligne.append(celluleActions);

  return ligne;
}

async function forcerLaDeconnexion(identifiant) {
  comptesErreur.hidden = true;
  deconnexionForceeConfirmation.hidden = true;

  let reponse;
  try {
    reponse = await fetch(`/comptes/${encodeURIComponent(identifiant)}/deconnexion-forcee`, {
      method: "POST",
    });
  } catch {
    comptesErreur.textContent = "Impossible de joindre le service de gestion des comptes. Réessayez plus tard.";
    comptesErreur.hidden = false;
    return;
  }

  if (reponse.status === 401) {
    afficherEcranConnexion();
    return;
  }

  if (!reponse.ok) {
    const detail = await reponse.json().catch(() => null);
    comptesErreur.textContent =
      detail && typeof detail.detail === "string"
        ? detail.detail
        : "La déconnexion forcée a échoué. Réessayez plus tard.";
    comptesErreur.hidden = false;
    return;
  }

  deconnexionForceeIdentifiant.textContent = identifiant;
  deconnexionForceeConfirmation.hidden = false;
}

async function reinitialiserMotDePasse(identifiant) {
  comptesErreur.hidden = true;
  motDePasseReinitialise.hidden = true;

  let reponse;
  try {
    reponse = await fetch(`/comptes/${encodeURIComponent(identifiant)}/reinitialiser-mot-de-passe`, {
      method: "POST",
    });
  } catch {
    comptesErreur.textContent = "Impossible de joindre le service de gestion des comptes. Réessayez plus tard.";
    comptesErreur.hidden = false;
    return;
  }

  if (reponse.status === 401) {
    afficherEcranConnexion();
    return;
  }

  if (!reponse.ok) {
    const detail = await reponse.json().catch(() => null);
    comptesErreur.textContent =
      detail && typeof detail.detail === "string"
        ? detail.detail
        : "La réinitialisation du mot de passe a échoué. Réessayez plus tard.";
    comptesErreur.hidden = false;
    return;
  }

  const corps = await reponse.json();
  motDePasseReinitialiseIdentifiant.textContent = identifiant;
  motDePasseReinitialiseValeur.textContent = corps.mot_de_passe;
  motDePasseReinitialise.hidden = false;
}

function ouvrirModificationCompte(identifiant) {
  const compte = comptesActuels.find((candidat) => candidat.identifiant === identifiant);
  if (!compte) {
    return;
  }

  identifiantEnCoursDeModification = identifiant;
  modificationErreur.hidden = true;
  modificationIdentifiant.textContent = identifiant;
  formulaireModificationCompte.elements.prenom.value = compte.prenom;
  formulaireModificationCompte.elements.nom.value = compte.nom;
  formulaireModificationCompte.elements.email.value = compte.email || "";
  formulaireModificationCompte.elements.agence.value = compte.agence;
  for (const case_ of formulaireModificationCompte.querySelectorAll('input[name="poles"]')) {
    case_.checked = compte.poles.includes(case_.value);
  }

  modificationTitre.hidden = false;
  formulaireModificationCompte.hidden = false;
}

function fermerModificationCompte() {
  identifiantEnCoursDeModification = null;
  modificationTitre.hidden = true;
  formulaireModificationCompte.hidden = true;
  formulaireModificationCompte.reset();
  modificationErreur.hidden = true;
}

function ouvrirChangementStatutAdmin(identifiant, nouveauEstAdmin) {
  identifiantEnCoursDeChangementStatutAdmin = identifiant;
  estAdminCibleEnCours = nouveauEstAdmin;
  statutAdminErreur.hidden = true;
  statutAdminConfirmation.hidden = true;
  statutAdminAction.textContent = nouveauEstAdmin ? "Promouvoir" : "Rétrograder";
  statutAdminIdentifiant.textContent = identifiant;
  statutAdminTitre.hidden = false;
  formulaireStatutAdmin.hidden = false;
  statutAdminCle.focus();
}

function fermerChangementStatutAdmin() {
  identifiantEnCoursDeChangementStatutAdmin = null;
  estAdminCibleEnCours = null;
  statutAdminTitre.hidden = true;
  formulaireStatutAdmin.hidden = true;
  formulaireStatutAdmin.reset();
  statutAdminErreur.hidden = true;
}

async function chargerComptes() {
  comptesErreur.hidden = true;

  let reponse;
  try {
    reponse = await fetch("/comptes");
  } catch {
    comptesErreur.textContent = "Impossible de joindre le service de gestion des comptes. Réessayez plus tard.";
    comptesErreur.hidden = false;
    return;
  }

  if (reponse.status === 401) {
    afficherEcranConnexion();
    return;
  }

  if (!reponse.ok) {
    const detail = await reponse.json().catch(() => null);
    comptesErreur.textContent =
      detail && detail.detail ? detail.detail : "Le chargement des comptes a échoué. Réessayez plus tard.";
    comptesErreur.hidden = false;
    return;
  }

  const comptes = await reponse.json();
  comptesActuels = comptes;
  corpsTableauComptes.replaceChildren(...comptes.map(ligneCompte));
}

formulaireCreationCompte.addEventListener("submit", async (evenement) => {
  evenement.preventDefault();
  creationErreur.hidden = true;
  compteCree.hidden = true;

  const donnees = new FormData(formulaireCreationCompte);
  const poles = donnees.getAll("poles");
  if (poles.length === 0) {
    creationErreur.textContent = "Sélectionnez au moins un pôle.";
    creationErreur.hidden = false;
    return;
  }

  const email = donnees.get("email");
  const corpsRequete = {
    identifiant: donnees.get("identifiant"),
    prenom: donnees.get("prenom"),
    nom: donnees.get("nom"),
    email: email ? email : null,
    agence: donnees.get("agence"),
    poles,
  };

  let reponse;
  try {
    reponse = await fetch("/comptes", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(corpsRequete),
    });
  } catch {
    creationErreur.textContent = "Impossible de joindre le service de gestion des comptes. Réessayez plus tard.";
    creationErreur.hidden = false;
    return;
  }

  if (reponse.status === 401) {
    afficherEcranConnexion();
    return;
  }

  if (!reponse.ok) {
    const detail = await reponse.json().catch(() => null);
    creationErreur.textContent =
      detail && typeof detail.detail === "string"
        ? detail.detail
        : "La création du compte a échoué. Réessayez plus tard.";
    creationErreur.hidden = false;
    return;
  }

  const compte = await reponse.json();
  formulaireCreationCompte.reset();
  compteCreeMotDePasse.textContent = compte.mot_de_passe;
  compteCree.hidden = false;
  await chargerComptes();
});

modificationAnnuler.addEventListener("click", fermerModificationCompte);

formulaireModificationCompte.addEventListener("submit", async (evenement) => {
  evenement.preventDefault();
  modificationErreur.hidden = true;

  const donnees = new FormData(formulaireModificationCompte);
  const poles = donnees.getAll("poles");
  if (poles.length === 0) {
    modificationErreur.textContent = "Sélectionnez au moins un pôle.";
    modificationErreur.hidden = false;
    return;
  }

  const email = donnees.get("email");
  const corpsRequete = {
    prenom: donnees.get("prenom"),
    nom: donnees.get("nom"),
    email: email ? email : null,
    agence: donnees.get("agence"),
    poles,
  };

  let reponse;
  try {
    reponse = await fetch(`/comptes/${encodeURIComponent(identifiantEnCoursDeModification)}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(corpsRequete),
    });
  } catch {
    modificationErreur.textContent = "Impossible de joindre le service de gestion des comptes. Réessayez plus tard.";
    modificationErreur.hidden = false;
    return;
  }

  if (reponse.status === 401) {
    afficherEcranConnexion();
    return;
  }

  if (!reponse.ok) {
    const detail = await reponse.json().catch(() => null);
    modificationErreur.textContent =
      detail && typeof detail.detail === "string"
        ? detail.detail
        : "La modification du compte a échoué. Réessayez plus tard.";
    modificationErreur.hidden = false;
    return;
  }

  fermerModificationCompte();
  await chargerComptes();
});

statutAdminAnnuler.addEventListener("click", fermerChangementStatutAdmin);

formulaireStatutAdmin.addEventListener("submit", async (evenement) => {
  evenement.preventDefault();
  statutAdminErreur.hidden = true;

  const cleAdminVm = statutAdminCle.value;
  const corpsRequete = { est_admin: estAdminCibleEnCours, cle_admin_vm: cleAdminVm };

  let reponse;
  try {
    reponse = await fetch(`/comptes/${encodeURIComponent(identifiantEnCoursDeChangementStatutAdmin)}/est-admin`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(corpsRequete),
    });
  } catch {
    statutAdminErreur.textContent = "Impossible de joindre le service de gestion des comptes. Réessayez plus tard.";
    statutAdminErreur.hidden = false;
    return;
  }

  if (reponse.status === 401) {
    afficherEcranConnexion();
    return;
  }

  if (!reponse.ok) {
    const detail = await reponse.json().catch(() => null);
    statutAdminErreur.textContent =
      detail && typeof detail.detail === "string"
        ? detail.detail
        : "Le changement de statut administrateur a échoué. Réessayez plus tard.";
    statutAdminErreur.hidden = false;
    return;
  }

  const compte = await reponse.json();
  statutAdminConfirmationIdentifiant.textContent = compte.identifiant;
  statutAdminConfirmationStatut.textContent = compte.est_admin ? "administrateur" : "un compte normal";
  fermerChangementStatutAdmin();
  statutAdminConfirmation.hidden = false;
  await chargerComptes();
});

function ouvrirSuppressionCompte(identifiant) {
  identifiantEnCoursDeSuppression = identifiant;
  suppressionErreur.hidden = true;
  suppressionConfirmation.hidden = true;
  suppressionIdentifiant.textContent = identifiant;
  suppressionTitre.hidden = false;
  formulaireSuppressionCompte.hidden = false;
  suppressionCle.focus();
}

function fermerSuppressionCompte() {
  identifiantEnCoursDeSuppression = null;
  suppressionTitre.hidden = true;
  formulaireSuppressionCompte.hidden = true;
  formulaireSuppressionCompte.reset();
  suppressionErreur.hidden = true;
}

suppressionAnnuler.addEventListener("click", fermerSuppressionCompte);

formulaireSuppressionCompte.addEventListener("submit", async (evenement) => {
  evenement.preventDefault();
  suppressionErreur.hidden = true;

  const cleAdminVm = suppressionCle.value;
  // Capturé avant l'attente réseau : si l'administrateur ouvre la
  // confirmation d'un autre compte pendant que cette requête est en vol,
  // identifiantEnCoursDeSuppression aura changé (voir ouvrirSuppressionCompte)
  // et ne doit pas être relu après coup, au risque d'attribuer la suppression
  // au mauvais compte.
  const identifiantSupprime = identifiantEnCoursDeSuppression;

  let reponse;
  try {
    reponse = await fetch(`/comptes/${encodeURIComponent(identifiantSupprime)}`, {
      method: "DELETE",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ cle_admin_vm: cleAdminVm }),
    });
  } catch {
    suppressionErreur.textContent = "Impossible de joindre le service de gestion des comptes. Réessayez plus tard.";
    suppressionErreur.hidden = false;
    return;
  }

  if (reponse.status === 401) {
    afficherEcranConnexion();
    return;
  }

  if (!reponse.ok) {
    const detail = await reponse.json().catch(() => null);
    suppressionErreur.textContent =
      detail && typeof detail.detail === "string"
        ? detail.detail
        : "La suppression du compte a échoué. Réessayez plus tard.";
    suppressionErreur.hidden = false;
    return;
  }

  // Ne referme le formulaire que s'il concerne toujours le compte qu'on
  // vient de supprimer : l'administrateur a pu, pendant la requête, ouvrir la
  // confirmation d'un autre compte (voir capture d'identifiantSupprime
  // ci-dessus), auquel cas cette saisie en cours ne doit pas être perdue.
  if (identifiantEnCoursDeSuppression === identifiantSupprime) {
    fermerSuppressionCompte();
  }
  suppressionConfirmationIdentifiant.textContent = identifiantSupprime;
  suppressionConfirmation.hidden = false;
  await chargerComptes();
});

verifierSessionActive();
