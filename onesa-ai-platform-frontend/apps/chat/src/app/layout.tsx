import { DraftNavigationProvider } from "../components/draft-navigation";
import { CompanyFooter } from "../components/company-footer";
import type { Metadata } from "next";
import {company} from "../lib/company";
import "./globals.css";
import { cookies } from "next/headers";
import { LocaleProvider, type Locale } from "../lib/i18n";
import { OnesaIdentityProvider } from "../components/onesa-sign-in";
import { loadIdentityMethod } from "../lib/server/identity-method";
export const dynamic = "force-dynamic";
export const metadata: Metadata = {
  title: { default: "Chat | Onesa AI Platform", template: "%s | Onesa AI Platform" },
  robots: { index: false, follow: false },
  description:
    "Onesa AI Platform: private Chat, Knowledge, Agents and Travel workspaces with configurable inference providers.",
  icons: {
    icon: [{url: "/brand/icons/v1/onesa-ai.svg", type: "image/svg+xml", sizes: "any"}],
    shortcut: "/favicon.ico",
    apple: [{url: "/brand/icons/v1/onesa-ai-180.png", type: "image/png", sizes: "180x180"}],
  },
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
  const [preferences, identityMethod] = await Promise.all([cookies(), loadIdentityMethod()]);
  const preference = preferences.get("onesa_ui_locale")?.value;
  const locale: Locale =
    preference === "en" || preference === "de" ? preference : configured;
  return (
    <html lang={locale} data-onesa-product="ai" data-onesa-environment={process.env.VERCEL_ENV === "production" ? "production" : process.env.VERCEL_ENV === "preview" ? "staging" : undefined}>
      <body>
        {(() => {
          const environment = process.env.VERCEL_ENV === "preview" ? "STAGING" : process.env.NODE_ENV === "development" || process.env.VERCEL_ENV === "development" ? "DEVELOPMENT" : null;
          return environment ? <div className="environment-context" role="region" aria-label="Deployment context">{environment} · Onesa AI Platform</div> : null;
        })()}
        <LocaleProvider initialLocale={locale}>
          <OnesaIdentityProvider initialMethod={identityMethod}>
            <DraftNavigationProvider>{children}</DraftNavigationProvider>
          </OnesaIdentityProvider>
          <CompanyFooter legalName={company.legalName} />
        </LocaleProvider>
      </body>
    </html>
  );
}
