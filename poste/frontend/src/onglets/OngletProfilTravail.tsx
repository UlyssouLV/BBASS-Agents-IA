import { useProfilTravailQuery } from "@/hooks/useProfilTravail";
import { ErreurApi } from "@/lib/api";

// Réécriture React de la section #onglet-profil-travail d'app.js : lecture
// seule, contenu vide ("") affiché comme « aucun profil enregistré » (voir
// docs/specs/v1.2.0-interface-poste.md et issue #64).
export function OngletProfilTravail() {
  const profilTravailQuery = useProfilTravailQuery();

  if (profilTravailQuery.isLoading) {
    return <output>Chargement…</output>;
  }

  if (profilTravailQuery.error) {
    const message =
      profilTravailQuery.error instanceof ErreurApi
        ? profilTravailQuery.error.message
        : "Le chargement du profil de travail a échoué. Réessayez plus tard.";
    return (
      <p role="alert" className="text-sm text-destructive">
        {message}
      </p>
    );
  }

  const profil = profilTravailQuery.data;
  if (!profil) {
    return null;
  }

  if (!profil.contenu) {
    return <p className="text-sm text-muted-foreground">Aucun profil de travail enregistré pour le moment.</p>;
  }

  return (
    <div>
      <p className="text-sm">{profil.contenu}</p>
      {profil.date_derniere_maj && (
        <p className="mt-2 text-xs text-muted-foreground">
          Dernière mise à jour : {new Date(profil.date_derniere_maj).toLocaleString()}
        </p>
      )}
    </div>
  );
}
