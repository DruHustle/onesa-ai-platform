"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useLocale } from "../lib/i18n";

/** Navigation reflects this API and account's access; the API still authorizes every operation. */
export default function IndustrialNav() {
  const { copy } = useLocale();
  const pathname = usePathname();
  const [available, setAvailable] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    const deadline = setTimeout(() => controller.abort(), 8000);
    fetch("/api/v1/industrial/assets", {
      credentials: "same-origin", cache: "no-store", signal: controller.signal,
    })
      .then(response => response.status === 200 ? response.json() : null)
      .then(result => { if (active) setAvailable(Array.isArray(result?.items) && result.items.every((item: unknown) => typeof item === "object" && item !== null && "id" in item && typeof item.id === "string" && item.id.length > 0 && "name" in item && typeof item.name === "string" && item.name.length > 0)); })
      .catch(() => { if (active) setAvailable(false); })
      .finally(() => clearTimeout(deadline));
    return () => { active = false; controller.abort(); clearTimeout(deadline); };
  }, []);
  return available ? <Link href="/industrial" aria-current={pathname === "/industrial" ? "page" : undefined}>{copy.industrial}</Link> : null;
}
