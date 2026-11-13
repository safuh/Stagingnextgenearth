import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "NextGen for Earth",
  description: "Research, learning and environmental impact platform.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
