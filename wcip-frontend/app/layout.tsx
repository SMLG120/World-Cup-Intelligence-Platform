import type { Metadata } from "next";
import { Bricolage_Grotesque, Hanken_Grotesk, IBM_Plex_Mono } from "next/font/google";
import "./globals.css";
import { Providers } from "./providers";
import { Nav } from "@/components/nav";

const display = Bricolage_Grotesque({
  subsets: ["latin"], variable: "--font-display", display: "swap",
});
const body = Hanken_Grotesk({
  subsets: ["latin"], variable: "--font-body", display: "swap",
});
const mono = IBM_Plex_Mono({
  subsets: ["latin"], weight: ["400", "500", "600"], variable: "--font-mono", display: "swap",
});

export const metadata: Metadata = {
  title: "World Cup Intelligence Platform",
  description:
    "Statistical simulation for World Cup match and tournament prediction. Educational analysis, not betting advice.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${display.variable} ${body.variable} ${mono.variable}`}>
      <body className="font-sans antialiased">
        <Providers>
          <div className="app-root min-h-screen flex flex-col">
            <Nav />
            <main className="flex-1 mx-auto w-full max-w-6xl px-5 py-8">{children}</main>
            <footer className="border-t border-line">
              <div className="mx-auto max-w-6xl px-5 py-5 flex flex-wrap gap-2 justify-between text-xs text-muted">
                <span className="kicker">World Cup Intelligence Platform</span>
                <span>Statistical simulation for education — not betting advice.</span>
              </div>
            </footer>
          </div>
        </Providers>
      </body>
    </html>
  );
}
