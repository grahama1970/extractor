import "./globals.css";
import "@excalidraw/excalidraw/index.css";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Gold Annotator (React)",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-white antialiased">{children}</body>
    </html>
  );
}

