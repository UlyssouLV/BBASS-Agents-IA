const ecranConnexion = document.getElementById("ecran-connexion");
const ecranCompte = document.getElementById("ecran-compte");
const formulaireConnexion = document.getElementById("formulaire-connexion");
const erreurConnexion = document.getElementById("erreur-connexion");
const identifiantConnecte = document.getElementById("identifiant-connecte");
const boutonDeconnexion = document.getElementById("bouton-deconnexion");
const avertissementSession = document.getElementById("avertissement-session");
const messages = document.getElementById("messages");
const chatChargement = document.getElementById("chat-chargement");
const chatErreur = document.getElementById("chat-erreur");
const formulaireChat = document.getElementById("formulaire-chat");
const champMessage = document.getElementById("message");

function afficherEcranCompte(compte) {
  identifiantConnecte.textContent = `${compte.prenom} ${compte.nom} (${compte.identifiant})`;
  if (compte.avertissement) {
    avertissementSession.textContent = compte.avertissement;
    avertissementSession.hidden = false;
  } else {
    avertissementSession.hidden = true;
  }
  ecranConnexion.hidden = true;
  ecranCompte.hidden = false;
}

function afficherEcranConnexion() {
  ecranConnexion.hidden = false;
  ecranCompte.hidden = true;
  erreurConnexion.hidden = true;
  messages.replaceChildren();
  chatErreur.hidden = true;
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

verifierSessionActive();
