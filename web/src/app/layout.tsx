import type { Metadata } from "next";
import { Fraunces, IBM_Plex_Mono, Outfit } from "next/font/google";
import "./globals.css";

const outfit = Outfit({
  variable: "--font-source",
  subsets: ["latin"],
});

const fraunces = Fraunces({
  variable: "--font-fraunces",
  subsets: ["latin"],
});

const plex = IBM_Plex_Mono({
  variable: "--font-plex",
  subsets: ["latin"],
  weight: ["400", "500"],
});

export const metadata: Metadata = {
  title: "RepoMind — local repository investigations",
  description:
    "Specialist agents read a Python repository on your machine, a critic rejects the theory that does not explain the symptom, and a patch counts only after the tests go from failing to passing.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${outfit.variable} ${fraunces.variable} ${plex.variable} h-full antialiased`}
    >
      <body className="desk-grid min-h-full font-sans text-[#ebe6d8]">{children}</body>
    </html>
  );
}
