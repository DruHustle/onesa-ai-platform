import type { Metadata } from "next";
import "./globals.css";
import {dayNightBoot} from "../lib/day-night-boot";
import {headers} from "next/headers";
import { cookies } from "next/headers";
import { LocaleProvider, type Locale } from "../lib/i18n";
export const dynamic = "force-dynamic";
export const metadata: Metadata = {
  title: "Onesa AI",
  robots: { index: false, follow: false },
  description:
    "A European-based, modular, self-hosted AI platform for European and international applications",
};
export default async function Layout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  const configured = process.env.ONESA_UI_LOCALE || "en";
  if (configured !== "en" && configured !== "de") {
    throw new Error(
      "ONESA_UI_LOCALE must name an available interface catalog: en or de",
    );
  }
  const preference = (await cookies()).get("onesa_ui_locale")?.value;
  const locale: Locale =
    preference === "en" || preference === "de" ? preference : configured;
  return (
    <html lang={locale} suppressHydrationWarning>
      <head><script nonce={(await headers()).get("x-nonce")||undefined} dangerouslySetInnerHTML={{__html:dayNightBoot}}/></head>
      <body>
        <LocaleProvider initialLocale={locale}>{children}</LocaleProvider>
      </body>
    </html>
  );
}
