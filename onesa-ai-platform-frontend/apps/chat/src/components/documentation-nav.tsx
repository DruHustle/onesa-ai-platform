"use client";
import { useEffect, useState } from "react";
import { documentationUrls } from "../lib/documentation";
import { useLocale } from "../lib/i18n";
export default function DocumentationNav() {
  const { copy } = useLocale();
  const [engineering, setEngineering] = useState(false);
  useEffect(() => {
    fetch("/api/v1/documentation/access")
      .then((r) => (r.ok ? r.json() : null))
      .then((v) => setEngineering(Boolean(v?.engineering)))
      .catch(() => {});
  }, []);
  return (
    <>
      <a href={documentationUrls.public}>{copy.documentation}</a>
      {engineering && (
        <a href={documentationUrls.internal}>{copy.engineeringDocumentation}</a>
      )}
    </>
  );
}
