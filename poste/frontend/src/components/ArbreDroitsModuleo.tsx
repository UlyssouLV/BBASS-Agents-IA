import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import type { CategorieDroitsModuleo, ConditionsModuleo, DroitCatalogueModuleo } from "@/hooks/useModuleo";

// Cases cochées d'un groupe : chemin → conditions Planning posées (ou null).
export type DroitsCoches = Map<string, ConditionsModuleo | null>;

const OPERATEURS = ["Fait partie", "Ne fait pas partie"];

interface ValeurListe {
  operateur: string;
  [cle: string]: unknown;
}

// Clé de la liste d'un champ « … des activités suivantes » / « … aux
// groupes suivants » : celle déjà en base si elle existe (forme de
// catalogue.json), sinon déduite du libellé.
function cleDeListe(champ: string, valeur: unknown): string {
  if (valeur && typeof valeur === "object") {
    const existante = Object.keys(valeur).find((cle) => cle !== "operateur");
    if (existante) {
      return existante;
    }
  }
  return /activit/i.test(champ) ? "activites" : "groupes";
}

function ChampCondition({
  champ,
  valeur,
  onChange,
}: Readonly<{ champ: string; valeur: unknown; onChange: (valeur: unknown) => void }>) {
  const coche = valeur !== undefined;
  // « … » : le champ attend un opérateur et une liste, sinon une case.
  const avecListe = champ.includes("…");
  const cle = cleDeListe(champ, valeur);
  const liste = avecListe && coche ? (valeur as ValeurListe) : null;
  const elements = liste && Array.isArray(liste[cle]) ? (liste[cle] as string[]) : [];

  return (
    <div className="ml-6 flex flex-wrap items-center gap-2 text-xs">
      <label className="flex items-center gap-2">
        <Checkbox
          checked={coche}
          onCheckedChange={(etat) =>
            onChange(etat === true ? (avecListe ? { operateur: OPERATEURS[0], [cle]: [] } : true) : undefined)
          }
        />
        {champ}
      </label>
      {liste && (
        <>
          <select
            aria-label={`Opérateur — ${champ}`}
            className="h-7 rounded-md border border-input bg-transparent px-2"
            value={liste.operateur}
            onChange={(e) => onChange({ ...liste, operateur: e.target.value })}
          >
            {OPERATEURS.map((operateur) => (
              <option key={operateur}>{operateur}</option>
            ))}
          </select>
          <Input
            aria-label={`Valeurs — ${champ}`}
            className="h-7 w-56 text-xs"
            placeholder="CHANTIER, ABSENCE"
            defaultValue={elements.join(", ")}
            onBlur={(e) =>
              onChange({
                ...liste,
                [cle]: e.target.value
                  .split(",")
                  .map((element) => element.trim())
                  .filter(Boolean),
              })
            }
          />
        </>
      )}
    </div>
  );
}

function EditeurConditions({
  proposees,
  conditions,
  onChange,
}: Readonly<{
  proposees: Record<string, string[]>;
  conditions: ConditionsModuleo | null;
  onChange: (conditions: ConditionsModuleo | null) => void;
}>) {
  function poser(condition: string, valeur: Record<string, unknown> | undefined) {
    const suivantes = { ...conditions };
    if (valeur === undefined) {
      delete suivantes[condition];
    } else {
      suivantes[condition] = valeur;
    }
    onChange(Object.keys(suivantes).length > 0 ? suivantes : null);
  }

  return (
    <div className="ml-6 space-y-1 border-l pl-3">
      {Object.entries(proposees).map(([condition, champs]) => {
        const posee = conditions?.[condition];
        return (
          <div key={condition} className="space-y-1">
            <label className="flex items-center gap-2 text-xs italic">
              <Checkbox checked={posee !== undefined} onCheckedChange={(etat) => poser(condition, etat === true ? {} : undefined)} />
              {condition}
            </label>
            {posee !== undefined &&
              champs.map((champ) => (
                <ChampCondition
                  key={champ}
                  champ={champ}
                  valeur={posee[champ]}
                  onChange={(valeur) => {
                    const champsPoses = { ...posee };
                    if (valeur === undefined) {
                      delete champsPoses[champ];
                    } else {
                      champsPoses[champ] = valeur;
                    }
                    poser(condition, champsPoses);
                  }}
                />
              ))}
          </div>
        );
      })}
    </div>
  );
}

function decocher(droit: DroitCatalogueModuleo, coches: DroitsCoches) {
  coches.delete(droit.chemin);
  for (const sousDroit of droit.sous_droits) {
    decocher(sousDroit, coches);
  }
}

function NoeudDroit({
  droit,
  coches,
  onChange,
  desactive = false,
}: Readonly<{
  droit: DroitCatalogueModuleo;
  coches: DroitsCoches;
  onChange: (coches: DroitsCoches) => void;
  desactive?: boolean;
}>) {
  const coche = coches.has(droit.chemin);

  function poser(conditions: ConditionsModuleo | null | undefined) {
    const suivantes = new Map(coches);
    if (conditions === undefined) {
      // Comme dans Moduléo : décocher un droit décoche ses sous-droits.
      decocher(droit, suivantes);
    } else {
      suivantes.set(droit.chemin, conditions);
    }
    onChange(suivantes);
  }

  return (
    <li className="space-y-1">
      <label className="flex items-center gap-2 text-sm">
        <Checkbox
          checked={coche}
          disabled={desactive}
          onCheckedChange={(etat) => poser(etat === true ? null : undefined)}
        />
        {droit.libelle}
      </label>
      {coche && droit.conditions && Object.keys(droit.conditions).length > 0 && (
        <EditeurConditions
          proposees={droit.conditions}
          conditions={coches.get(droit.chemin) ?? null}
          onChange={poser}
        />
      )}
      {droit.sous_droits.length > 0 && (
        <ul className="ml-6 space-y-1">
          {droit.sous_droits.map((sousDroit) => (
            <NoeudDroit key={sousDroit.chemin} droit={sousDroit} coches={coches} onChange={onChange} desactive={!coche} />
          ))}
        </ul>
      )}
    </li>
  );
}

// Arborescence façon Moduléo (catégories, actions, sous-droits) des cases
// déjà en base : on coche, on ne crée ni ne renomme jamais une case
// (catalogue en lecture seule, ADR-0019).
export function ArbreDroitsModuleo({
  categories,
  coches,
  onChange,
}: Readonly<{ categories: CategorieDroitsModuleo[]; coches: DroitsCoches; onChange: (coches: DroitsCoches) => void }>) {
  return (
    <div className="space-y-4">
      {categories.map((categorie) => (
        <section key={categorie.categorie}>
          <h4 className="mb-1 text-sm font-semibold">{categorie.categorie}</h4>
          <ul className="space-y-1">
            {categorie.droits.map((droit) => (
              <NoeudDroit key={droit.chemin} droit={droit} coches={coches} onChange={onChange} />
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}
