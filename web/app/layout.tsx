import type { Metadata } from "next";
import { Instrument_Serif, IBM_Plex_Mono, IBM_Plex_Sans } from "next/font/google";
import "./globals.css";

const serif = Instrument_Serif({ weight: "400", subsets: ["latin"], variable: "--font-serif", display: "swap" });
const mono = IBM_Plex_Mono({ weight: ["400", "500", "600"], subsets: ["latin"], variable: "--font-mono", display: "swap" });
const sans = IBM_Plex_Sans({ weight: ["400", "500"], subsets: ["latin"], variable: "--font-sans", display: "swap" });

const TITLE = "Beacon — the reference rate for AI inference";
const DESC = "What a unit of intelligence costs: a capability-normalized price reference rate across every major AI model — updated daily and published on-chain.";

export const metadata: Metadata = {
  metadataBase: new URL("https://zhijiewong.github.io/beacon-index/"),
  title: TITLE,
  description: DESC,
  openGraph: {
    title: TITLE,
    description: DESC,
    url: "https://zhijiewong.github.io/beacon-index/",
    siteName: "Beacon",
    type: "website",
    images: [{ url: "og.png", width: 1200, height: 630, alt: TITLE }],
  },
  twitter: {
    card: "summary_large_image",
    title: TITLE,
    description: DESC,
    images: ["og.png"],
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${serif.variable} ${mono.variable} ${sans.variable}`}>
      <body className="font-sans antialiased">{children}</body>
    </html>
  );
}
