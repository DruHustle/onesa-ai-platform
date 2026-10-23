"use client";
import ApplicationsNav from "./applications-nav";
import ProductionWorkspaceCue from "./production-workspace-cue";
import DocumentationNav from "./documentation-nav";
import IndustrialNav from "./industrial-nav";
import DocumentationHelp from "./documentation-help";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { LanguageSelect, useLocale } from "../lib/i18n";
export default function FeatureShell({
  title,
  children,
  contentLang = "en",
}: {
  title: string;
  children: React.ReactNode;
  contentLang?: "en" | "de";
}) {
  const { copy } = useLocale();
  const pathname = usePathname();
  return (
    <main className="feature-shell">
      <header>
        <Link href="/" className="brand">
          Onesa <span>AI Platform</span>
        </Link>
        <nav aria-label="AI workspace">
          <Link href="/" aria-current={pathname === "/" ? "page" : undefined}>{copy.chat}</Link>
          <Link href="/knowledge" aria-current={pathname === "/knowledge" ? "page" : undefined}>{copy.knowledge}</Link>
          <Link href="/agents" aria-current={pathname === "/agents" ? "page" : undefined}>{copy.agents}</Link>
          <Link href="/travel" aria-current={pathname === "/travel" ? "page" : undefined}>{copy.travel}</Link>
          <IndustrialNav />
          <Link href="/settings" aria-current={pathname === "/settings" ? "page" : undefined}>Account settings</Link>
          <DocumentationNav />
        </nav>
        <ApplicationsNav />
        <LanguageSelect />
      </header>
      <section lang={contentLang}>
        <p className="eyebrow">Onesa AI Platform · {copy.workspace}</p>
        <h1>{title}</h1>
        <ProductionWorkspaceCue />
        {!title.toLowerCase().includes("settings") && pathname !== "/industrial" && (
          <DocumentationHelp
            topic={
              title.toLowerCase().includes("knowledge")
                ? "knowledge"
                : title.toLowerCase().includes("agent") ||
                    title.toLowerCase().includes("tool")
                  ? "agents"
                  : "travel"
            }
          />
        )}
        {children}
      </section>
    </main>
  );
}
