import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Ratio Chart - Financial Ratio Analysis",
  description: "Monitor financial ratio charts for Indian market traders",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="bg-bg-primary text-text-primary min-h-screen">
        {children}
      </body>
    </html>
  );
}
