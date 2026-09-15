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
const modificationTitre = document.getElementById("modification-titre");
const modificationIdentifiant = document.getElementById("modification-identifiant");
const formulaireModificationCompte = document.getElementById("formulaire-modification-compte");
const modificationErreur = document.getElementById("modification-erreur");
const modificationAnnuler = document.getElementById("modification-annuler");

let comptesActuels = [];
let identifiantEnCoursDeModification = null;

function afficherOngletChat() {
  ongletChat.hidden = false;
  ongletComptes.hidden = true;
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
  if (!message.trim()) {
    return;
  }

  ajouterMessage("collaborateur", message);
  champMessage.value = "";
  champMessage.disabled = true;
  chatChargement.hidden = false;

  try {
    let reponse;
    try {
      reponse = await fetch("/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message }),
      });
    } catch {
      chatErreur.textContent = "Impossible de joindre le service de chat. Réessayez plus tard.";
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
  ligne.append(celluleActions);

  return ligne;
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

verifierSessionActive();
