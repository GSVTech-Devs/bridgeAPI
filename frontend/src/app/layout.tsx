import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Bridge API",
  description: "Centralized API gateway management platform",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="pt-BR">
      <body>{children}</body>
    </html>
  );
}
