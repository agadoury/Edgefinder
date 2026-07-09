import type { Metadata } from "next";
import { GeistSans } from "geist/font/sans";
import { GeistMono } from "geist/font/mono";
import "./globals.css";
import { RevealProvider } from "../components/RevealContext";
import { PickemProvider, type PickemRow } from "../components/PickemContext";
import { Header } from "../components/Header";
import { Footer } from "../components/Footer";
import { getMeta, getSlate } from "../lib/data";

export const metadata: Metadata = {
  title: "EdgeFinder — Know what to expect before you bet",
  description:
    "AI projections for NFL player props, explained in plain English. Replaying the 2025 season so you can check every call against what actually happened.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const meta = getMeta();
  const slate = getSlate();
  // Compact per-prop index so the Pick 'em ledger can grade picks anywhere.
  const pickemRows: PickemRow[] = slate.props.map((p) => ({
    playerId: p.playerId,
    market: p.market,
    lean: p.lean,
    result: p.result,
  }));
  return (
    <html
      lang="en"
      className={`${GeistSans.variable} ${GeistMono.variable} h-full antialiased`}
    >
      <body className="flex min-h-full flex-col">
        <div className="bg-grid" aria-hidden />
        <RevealProvider>
          <PickemProvider season={slate.season} week={slate.week} rows={pickemRows}>
            <Header season={meta.season} week={meta.week} />
            <main className="flex-1">{children}</main>
            <Footer season={meta.season} modelVersion={meta.modelVersion} />
          </PickemProvider>
        </RevealProvider>
      </body>
    </html>
  );
}
