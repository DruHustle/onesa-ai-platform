"use client";
import { useEffect, useState } from "react";
import { documentationUrls } from "../lib/documentation";
import { useLocale } from "../lib/i18n";
export default function DocumentationNav() {
  const { copy, locale } = useLocale();
  const [access, setAccess] = useState({ engineering: false, independent: false });
  useEffect(() => {
    fetch("/api/v1/documentation/access")
      .then((r) => (r.ok ? r.json() : null))
      .then((v) => setAccess({
        engineering: v?.engineering === true,
        independent: v?.independent_documents === true,
      }))
      .catch(() => {});
  }, []);
  return (
    <>
      <a href={documentationUrls.public}>{copy.documentation}</a>
      {access.independent && (
        <a href={documentationUrls.independent}>
          {locale === "de" ? "Interne Dokumente" : "Internal Documents"}
        </a>
      )}
      {access.engineering && !access.independent && documentationUrls.internal && (
        <a href={documentationUrls.internal}>{copy.engineeringDocumentation}</a>
      )}
    </>
  );
}
