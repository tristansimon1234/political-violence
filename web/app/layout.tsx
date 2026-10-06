import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import type { ReactNode } from "react";

import "./globals.css";

// Polices auto-hébergées par Next au build (aucun appel à Google depuis le navigateur).
const geist = Geist({ subsets: ["latin"], variable: "--police-geist" });
const geistMono = Geist_Mono({ subsets: ["latin"], variable: "--police-geist-mono" });

export const metadata: Metadata = {
  title: "Radar 2027",
  robots: { index: false, follow: false },
};

export default function Layout({ children }: { children: ReactNode }) {
  return (
    <html lang="fr" className={`${geist.variable} ${geistMono.variable}`}>
      <body>{children}</body>
    </html>
  );
}
