"use client";

// Accès admin pour une page rendue côté serveur (contenu passé en enfants).
import type { ReactNode } from "react";

import { AccesAdmin } from "@/lib/AccesAdmin";

export function Protege({
  titre,
  retour,
  children,
}: {
  titre: string;
  retour: string;
  children: ReactNode;
}) {
  return (
    <AccesAdmin titre={titre} retour={retour}>
      {() => children}
    </AccesAdmin>
  );
}
