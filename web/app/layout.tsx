import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  metadataBase: new URL("https://nextgenforearth.org"),
  title: {
    default: "NextGen for Earth | Research, Learning & Environmental Action",
    template: "%s | NextGen for Earth",
  },
  description:
    "Connecting research, climate intelligence, learning and community-led environmental action for a more sustainable future.",
  applicationName: "NextGen for Earth",
  openGraph: {
    type: "website",
    siteName: "NextGen for Earth",
    title: "NextGen for Earth | Research, Learning & Environmental Action",
    description:
      "Connecting research, climate intelligence, learning and community-led environmental action for a more sustainable future.",
    url: "https://nextgenforearth.org/",
  },
  twitter: {
    card: "summary_large_image",
    title: "NextGen for Earth",
    description:
      "Research, climate intelligence, learning and community-led environmental action.",
  },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
