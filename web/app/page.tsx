import { redirect } from "next/navigation";

// Pas d'écran public tant que YouTube n'a pas accepté le cas d'usage « métriques dérivées ».
export default function Accueil() {
  redirect("/admin");
}
