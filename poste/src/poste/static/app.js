const ecranConnexion = document.getElementById("ecran-connexion");
const ecranCompte = document.getElementById("ecran-compte");
const formulaireConnexion = document.getElementById("formulaire-connexion");
const erreurConnexion = document.getElementById("erreur-connexion");
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
  ecranCompte.hidden = false;
}

function afficherEcranConnexion() {
  ecranConnexion.hidden = false;
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
  return ligne;
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

verifierSessionActive();
