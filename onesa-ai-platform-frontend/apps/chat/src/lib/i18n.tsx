"use client";

import { createContext, useContext, useState } from "react";

const english = {
  chat: "Chat",
  knowledge: "Knowledge",
  agents: "Agents",
  travel: "Travel",
  industrial: "Industrial AI",
  documentation: "Documentation",
  engineeringDocumentation: "Engineering docs",
  opening: "Opening Onesa AI…",
  createTitle: "Create your account",
  welcome: "Welcome back",
  description:
    "A modular, self-hosted AI platform for businesses, developers, and organizations.",
  name: "Display name",
  email: "Email",
  password: "Password",
  wait: "Please wait…",
  create: "Create account",
  signIn: "Sign in",
  existing: "Already have an account? Sign in",
  newAccount: "New to Onesa? Create an account",
  newConversation: "＋ New conversation",
  signOut: "Sign out",
  language: "Interface language",
  workspace: "ONESA WORKSPACE",
};
const german: typeof english = {
  chat: "Chat",
  knowledge: "Wissen",
  agents: "Agenten",
  travel: "Reisen",
  industrial: "Industrial AI",
  documentation: "Dokumentation",
  engineeringDocumentation: "Technische Dokumentation",
  opening: "Onesa AI wird geöffnet…",
  createTitle: "Konto erstellen",
  welcome: "Willkommen zurück",
  description:
    "Eine modulare, selbst gehostete KI-Plattform für Unternehmen, Entwickler und Organisationen.",
  name: "Anzeigename",
  email: "E-Mail",
  password: "Passwort",
  wait: "Bitte warten…",
  create: "Konto erstellen",
  signIn: "Anmelden",
  existing: "Bereits ein Konto? Anmelden",
  newAccount: "Neu bei Onesa? Konto erstellen",
  newConversation: "＋ Neues Gespräch",
  signOut: "Abmelden",
  language: "Sprache der Oberfläche",
  workspace: "ONESA ARBEITSBEREICH",
};
export const catalogs = { en: english, de: german };
export type Locale = keyof typeof catalogs;
const Context = createContext<{
  locale: Locale;
  copy: typeof english;
  changeLocale: (locale: Locale) => void;
}>({
  locale: "en" as Locale,
  copy: english,
  changeLocale: () => {},
});
export function LocaleProvider({
  initialLocale,
  children,
}: {
  initialLocale: Locale;
  children: React.ReactNode;
}) {
  const [locale, setLocale] = useState(initialLocale);
  function changeLocale(next: Locale) {
    setLocale(next);
    document.documentElement.lang = next;
    document.cookie = `onesa_ui_locale=${next}; Path=/; Max-Age=31536000; SameSite=Lax${location.protocol === "https:" ? "; Secure" : ""}`;
  }
  return (
    <Context.Provider value={{ locale, copy: catalogs[locale], changeLocale }}>
      {children}
    </Context.Provider>
  );
}
export const useLocale = () => useContext(Context);
export function LanguageSelect() {
  const { locale, copy, changeLocale } = useLocale();
  return (
    <label className="locale-select">
      {copy.language}
      <select
        value={locale}
        onChange={(e) => changeLocale(e.target.value as Locale)}
      >
        <option value="en">English</option>
        <option value="de">Deutsch (navigation / Anmeldung)</option>
      </select>
    </label>
  );
}
