import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { Suspense } from "react";
import { SiteHeader } from "@/components/SiteHeader";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin", "latin-ext", "vietnamese"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: { default: "Steam", template: "%s :: Steam" },
  description: "Steam game recommendation demo: per-user top-K (ALS / CB / Popularity) and similar games by tags.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="flex min-h-full flex-col font-sans">
        {/* Header và trang đọc cookie session nên phải nằm trong Suspense (Cache Components) */}
        <Suspense fallback={<div className="h-12 bg-topbar" />}>
          <SiteHeader />
        </Suspense>
        <main className="flex flex-1 flex-col">
          <Suspense>{children}</Suspense>
        </main>
      </body>
    </html>
  );
}
