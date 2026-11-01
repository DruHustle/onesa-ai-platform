"use client";
import ApplicationsNav from "./applications-nav";
import ProductionWorkspaceCue from "./production-workspace-cue";
import DocumentationNav from "./documentation-nav";
import IndustrialNav from "./industrial-nav";
import DocumentationHelp from "./documentation-help";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useId, useRef, useState } from "react";
import { LanguageSelect, useLocale } from "../lib/i18n";
export default function FeatureShell({
  title,
  children,
  contentLang = "en",
  wide = false,
}: {
  title: string;
  children: React.ReactNode;
  contentLang?: "en" | "de";
  wide?: boolean;
}) {
  const { copy, locale } = useLocale();
  const pathname = usePathname();
  const [optionsOpen, setOptionsOpen] = useState(false);
  const optionsId = useId();
  const optionsToggle = useRef<HTMLButtonElement | null>(null);
  return (
    <main
      className={wide ? "feature-shell feature-shell-wide" : "feature-shell"}
    >
      <header>
        <div className="feature-brand-row">
          <Link href="/" className="brand">
            Onesa <span>AI Platform</span>
          </Link>
          <button
            ref={optionsToggle}
            className="workspace-options-toggle"
            type="button"
            aria-expanded={optionsOpen}
            aria-controls={optionsId}
            onClick={() => setOptionsOpen(open => !open)}
          >
            {locale === "de" ? "Arbeitsbereich-Menü" : "Workspace options"}
          </button>
        </div>
        <nav aria-label="AI workspace">
          <Link href="/" aria-current={pathname === "/" ? "page" : undefined}>
            {copy.chat}
          </Link>
          <Link
            href="/knowledge"
            aria-current={pathname === "/knowledge" ? "page" : undefined}
          >
            {copy.knowledge}
          </Link>
          <Link
            href="/agents"
            aria-current={pathname === "/agents" ? "page" : undefined}
          >
            {copy.agents}
          </Link>
          <Link
            href="/travel"
            aria-current={pathname === "/travel" ? "page" : undefined}
          >
            {copy.travel}
          </Link>
          <IndustrialNav />
        </nav>
        <div
          id={optionsId}
          className={`workspace-tools${optionsOpen ? " open" : ""}`}
          onKeyDown={event => {
            if (event.key === "Escape" && optionsOpen) {
              event.preventDefault();
              setOptionsOpen(false);
              optionsToggle.current?.focus({ preventScroll: true });
            }
          }}
        >
          <nav className="workspace-resources" aria-label="Workspace resources">
            <Link
              href="/settings"
              prefetch={false}
              aria-current={pathname === "/settings" ? "page" : undefined}
            >
              Account settings
            </Link>
            <DocumentationNav />
          </nav>
          <ApplicationsNav />
          <LanguageSelect />
        </div>
      </header>
      <section lang={contentLang}>
        <p className="eyebrow">Onesa AI Platform · {copy.workspace}</p>
        <h1>{title}</h1>
        <ProductionWorkspaceCue />
        {!title.toLowerCase().includes("settings") &&
          !pathname.startsWith("/industrial") && (
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
