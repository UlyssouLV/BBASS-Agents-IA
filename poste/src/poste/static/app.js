const ecranConnexion = document.getElementById("ecran-connexion");
const ecranCompte = document.getElementById("ecran-compte");
const formulaireConnexion = document.getElementById("formulaire-connexion");
const erreurConnexion = document.getElementById("erreur-connexion");
const identifiantConnecte = document.getElementById("identifiant-connecte");
const boutonDeconnexion = document.getElementById("bouton-deconnexion");

function afficherEcranCompte(identifiant) {
  identifiantConnecte.textContent = identifiant;
  ecranConnexion.hidden = true;
  ecranCompte.hidden = false;
}

function afficherEcranConnexion() {
  ecranConnexion.hidden = false;
  ecranCompte.hidden = true;
  erreurConnexion.hidden = true;
}

async function verifierSessionActive() {
  const reponse = await fetch("/compte");
  if (reponse.ok) {
    const compte = await reponse.json();
    afficherEcranCompte(compte.identifiant);
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
  afficherEcranCompte(compte.identifiant);
});

boutonDeconnexion.addEventListener("click", async () => {
  await fetch("/deconnexion", { method: "POST" });
  afficherEcranConnexion();
});

verifierSessionActive();
