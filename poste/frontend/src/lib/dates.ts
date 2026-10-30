// Heures à Paris, le cabinet est en France, quel que soit le fuseau du
// navigateur (#256) : « 29 octobre 2026 à 12:07 ». La VM sert les dates en
// UTC avec leur fuseau.
const FORMAT_DATE_HEURE = new Intl.DateTimeFormat("fr-FR", {
  dateStyle: "long",
  timeStyle: "short",
  timeZone: "Europe/Paris",
});

export function formaterDateHeure(dateIso: string): string {
  return FORMAT_DATE_HEURE.format(new Date(dateIso));
}
