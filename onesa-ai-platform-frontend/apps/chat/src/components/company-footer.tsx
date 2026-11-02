"use client";

import { useLocale } from "../lib/i18n";

export function CompanyFooter({ legalName }: { legalName: string }) {
  const { locale } = useLocale();

  return (
    <footer className="company-footer">
      <span>{legalName}</span>
      <a href={`https://onesa.eu/${locale}/contact`}>
        {locale === "de" ? "Kontakt" : "Contact"}
      </a>
      <a href={`https://onesa.eu/${locale}/impressum`}>
        {locale === "de" ? "Impressum" : "Legal Notice"}
      </a>
      <a href={`https://onesa.eu/${locale}/privacy`}>
        {locale === "de" ? "Datenschutz" : "Privacy"}
      </a>
    </footer>
  );
}
