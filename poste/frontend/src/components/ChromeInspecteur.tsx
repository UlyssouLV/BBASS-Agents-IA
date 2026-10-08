import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

export function TitreInspecteur() {
  return <h1 className="mb-1 text-xl font-semibold">Inspecteur des échanges avec le modèle</h1>;
}

export function FilInspecteur({
  identifiant,
  titreConversation,
  onComptes,
  onCompte,
}: Readonly<{
  identifiant: string | null;
  titreConversation: string | null;
  onComptes: () => void;
  onCompte: () => void;
}>) {
  return (
    <nav aria-label="Fil d'Ariane" className="mb-4 flex flex-wrap items-center gap-1 text-sm text-muted-foreground">
      <button type="button" className="hover:underline" onClick={onComptes}>
        Comptes
      </button>
      {identifiant && (
        <>
          <span aria-hidden="true">/</span>
          <button type="button" className="hover:underline" onClick={onCompte}>
            {identifiant}
          </button>
        </>
      )}
      {titreConversation && (
        <>
          <span aria-hidden="true">/</span>
          <span className="text-foreground">{titreConversation}</span>
        </>
      )}
    </nav>
  );
}

export function EnTeteNiveau({
  titre,
  enCours,
  onRafraichir,
}: Readonly<{ titre: string; enCours: boolean; onRafraichir: () => void }>) {
  return (
    <div className="mb-4 flex items-center justify-between">
      <h2 className="text-sm font-semibold">{titre}</h2>
      <Button type="button" size="sm" variant="outline" disabled={enCours} onClick={onRafraichir}>
        Rafraîchir
      </Button>
    </div>
  );
}

export function TableauComptesInspecteur({
  identifiants,
  onChoisir,
}: Readonly<{ identifiants: string[]; onChoisir: (identifiant: string) => void }>) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Identifiant</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {identifiants.map((identifiant) => (
          <TableRow key={identifiant}>
            <TableCell>
              <button type="button" className="hover:underline" onClick={() => onChoisir(identifiant)}>
                {identifiant}
              </button>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

export interface LigneConversationInspecteur {
  id: number;
  titre: string;
  dateCreation: string;
  dateActivite: string;
}

export function TableauConversationsInspecteur({
  lignes,
  onChoisir,
}: Readonly<{ lignes: LigneConversationInspecteur[]; onChoisir: (id: number) => void }>) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Titre</TableHead>
          <TableHead>Créée le</TableHead>
          <TableHead>Dernière activité</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {lignes.map((ligne) => (
          <TableRow key={ligne.id}>
            <TableCell>
              <button type="button" className="text-left hover:underline" onClick={() => onChoisir(ligne.id)}>
                {ligne.titre}
              </button>
            </TableCell>
            <TableCell>{new Date(ligne.dateCreation).toLocaleString()}</TableCell>
            <TableCell>{new Date(ligne.dateActivite).toLocaleString()}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

export function CadrePageInspecteur({
  children,
  pleinEcran = true,
}: Readonly<{ children: ReactNode; pleinEcran?: boolean }>) {
  return (
    <main className={`mx-auto flex w-full max-w-5xl flex-col px-6 py-6 ${pleinEcran ? "h-svh" : ""}`}>{children}</main>
  );
}
