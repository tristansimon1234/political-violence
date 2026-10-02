"use client";

import type { Session } from "@supabase/supabase-js";
import { type FormEvent, type ReactNode, useEffect, useState } from "react";

import { supabase } from "@/lib/supabase";

// Accès réservé à l'admin (connexion par lien e-mail + table `admins`) : rien n'est public
// tant que YouTube n'a pas accepté le cas d'usage « métriques dérivées ».
export function AccesAdmin({
  titre,
  retour,
  children,
}: {
  titre: string;
  retour: string;
  children: (email: string) => ReactNode;
}) {
  const [session, setSession] = useState<Session | null>(null);
  const [chargee, setChargee] = useState(false);
  const [configuration, setConfiguration] = useState("");
  const [admin, setAdmin] = useState<boolean | null>(null);

  useEffect(() => {
    let client;
    try {
      client = supabase();
    } catch (e) {
      setConfiguration(e instanceof Error ? e.message : String(e));
      return;
    }
    client.auth.getSession().then(({ data }) => {
      setSession(data.session);
      setChargee(true);
    });
    const { data } = client.auth.onAuthStateChange((_e, s) => setSession(s));
    return () => data.subscription.unsubscribe();
  }, []);

  useEffect(() => {
    if (!session) return;
    void supabase()
      .rpc("est_admin")
      .then(({ data }) => setAdmin(Boolean(data)));
  }, [session]);

  if (configuration)
    return (
      <main>
        <h1>{titre}</h1>
        <p className="erreur">Configuration manquante : {configuration}</p>
        <p className="discret">
          Ajouter les variables dans Vercel (Settings → Environment Variables), puis redéployer.
        </p>
      </main>
    );
  if (!chargee) return <main className="discret">Chargement…</main>;
  if (!session) return <Connexion titre={titre} retour={retour} />;
  if (admin === null) return <main className="discret">Vérification de l'accès…</main>;
  if (!admin)
    return (
      <main>
        <h1>{titre}</h1>
        <p className="erreur">Ce compte n'est pas administrateur (table `admins`).</p>
      </main>
    );
  return <>{children(session.user.email ?? "")}</>;
}

function Connexion({ titre, retour }: { titre: string; retour: string }) {
  const [email, setEmail] = useState("");
  const [etat, setEtat] = useState<"saisie" | "envoye" | "erreur">("saisie");
  const [message, setMessage] = useState("");

  async function envoyer(e: FormEvent) {
    e.preventDefault();
    const { error } = await supabase().auth.signInWithOtp({
      email,
      options: { emailRedirectTo: `${window.location.origin}${retour}`, shouldCreateUser: false },
    });
    if (error) {
      setEtat("erreur");
      setMessage(error.message);
    } else {
      setEtat("envoye");
    }
  }

  return (
    <main>
      <h1>{titre}</h1>
      <p className="discret">Accès réservé. Connexion par lien envoyé par e-mail.</p>
      {etat === "envoye" ? (
        <p>Lien envoyé à {email}. Ouvre-le sur cet appareil.</p>
      ) : (
        <form className="connexion" onSubmit={envoyer}>
          <label htmlFor="email" className="discret">
            E-mail
          </label>
          <input
            id="email"
            type="email"
            required
            placeholder="e-mail"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
          <button className="petit" type="submit">
            Recevoir le lien
          </button>
        </form>
      )}
      {etat === "erreur" && <p className="erreur">{message}</p>}
    </main>
  );
}
