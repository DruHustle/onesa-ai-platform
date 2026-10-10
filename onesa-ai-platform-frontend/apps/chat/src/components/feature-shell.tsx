"use client";
import DocumentationNav from "./documentation-nav";
import DocumentationHelp from "./documentation-help";
import Link from "next/link";
import { LanguageSelect, useLocale } from "../lib/i18n";
export default function FeatureShell({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  const { copy } = useLocale();
  return (
    <main className="feature-shell">
      <header>
        <Link href="/" className="brand">
          Onesa <span>AI</span>
        </Link>
        <nav>
          <Link href="/">{copy.chat}</Link>
          <Link href="/knowledge">{copy.knowledge}</Link>
          <Link href="/agents">{copy.agents}</Link>
          <Link href="/travel">{copy.travel}</Link>
          <Link href="/settings">Account settings</Link>
          <DocumentationNav />
        </nav>
        <LanguageSelect />
      </header>
      <section lang="en">
        <p className="eyebrow">{copy.workspace}</p>
        <h1>{title}</h1>
        {!title.toLowerCase().includes("settings") && (
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
