"use client";

import { LanguageSelect, useLocale } from "../../lib/i18n";
import styles from "./overview.module.css";

const signInPath = "/?sign-in=1";
const registrationPath = "https://account.onesa.eu/register?product=ai&platform=web&audience=user";

const features = [
  {
    path: signInPath,
    en: ["Chat", "Ask questions, draft text and pick up saved conversations. Use the microphone and spoken playback where your browser supports them.", "A draft agenda turns three project updates into discussion topics."],
    de: ["Chat", "Stellen Sie Fragen, entwerfen Sie Texte und setzen Sie gespeicherte Gespräche fort. Mikrofon und Sprachausgabe hängen vom Browser ab.", "Aus drei Projektmeldungen entsteht ein Entwurf für die Tagesordnung."],
  },
  {
    path: "/knowledge",
    en: ["Knowledge", "Ask questions about documents in your workspace and follow citations to the source.", "An answer about a fictional office policy cites the section on travel expenses."],
    de: ["Wissen", "Stellen Sie Fragen zu Dokumenten im Arbeitsbereich und folgen Sie den Quellenangaben.", "Eine Antwort zu einer fiktiven Büroregel verweist auf den Abschnitt zu Reisekosten."],
  },
  {
    path: "/agents",
    en: ["Agents", "Review a task plan and approve consequential actions before an agent can run them.", "An agent proposes a checklist for a sample supplier review."],
    de: ["Agenten", "Prüfen Sie einen Aufgabenplan und genehmigen Sie folgenreiche Aktionen vor der Ausführung.", "Ein Agent schlägt eine Checkliste für die Prüfung eines Musterlieferanten vor."],
  },
  {
    path: "/work",
    en: ["Work", "Organize a larger request into steps and review the resulting work report.", "A sample handover is divided into open tasks, owners and dates."],
    de: ["Arbeiten", "Zerlegen Sie einen größeren Auftrag in Schritte und prüfen Sie den Arbeitsbericht.", "Eine fiktive Übergabe wird nach offenen Aufgaben, Zuständigkeiten und Terminen geordnet."],
  },
  {
    path: "/plugins",
    en: ["Plugins", "See which tools your workspace allows for AI tasks.", "A sample workspace permits document search for a drafting task."],
    de: ["Plugins", "Sehen Sie, welche Werkzeuge Ihr Arbeitsbereich für KI-Aufgaben freigibt.", "Ein Musterarbeitsbereich erlaubt die Dokumentensuche für einen Textentwurf."],
  },
  {
    path: "/travel",
    en: ["Travel", "Compare itinerary ideas and organize trip notes.", "A weekend outline groups activities by location and opening hours."],
    de: ["Reisen", "Vergleichen Sie Reiseideen und organisieren Sie Ihre Notizen.", "Ein Wochenendplan gruppiert Aktivitäten nach Standort und Öffnungszeiten."],
  },
  {
    path: "/industrial",
    en: ["Industrial AI", "Review asset context and trace investigation findings to their evidence.", "A simulated pump's reading is compared with a reference range."],
    de: ["Industrial AI", "Prüfen Sie Anlageninformationen und verfolgen Sie Befunde bis zu ihren Belegen zurück.", "Ein Messwert einer simulierten Pumpe wird mit dem Referenzbereich verglichen."],
  },
] as const;

export default function ProductOverview() {
  const { locale, copy } = useLocale();
  const german = locale === "de";
  return (
    <main className={styles.overview}>
      <header className={styles.header}>
        <h1>Onesa AI Platform</h1>
        <p>{german
          ? "Ein geschützter KI-Arbeitsbereich für Gespräche, Dokumente und Aufgaben."
          : "A private AI workspace for conversations, documents and tasks."}</p>
        <div className={styles.actions}>
          <a className={styles.primary} href={signInPath}>{copy.signIn}</a>
          <a href={registrationPath}>{copy.create}</a>
          <LanguageSelect />
        </div>
      </header>
      <section aria-labelledby="overview-features">
        <h2 id="overview-features">{german ? "Funktionen" : "Features"}</h2>
        <ul className={styles.features}>
          {features.map(feature => {
            const [title, description, example] = feature[locale];
            return (
              <li key={feature.path} className={styles.feature}>
                <h3>{title}</h3>
                <p>{description}</p>
                <details>
                  <summary>{german ? "Fiktives Beispiel" : "Synthetic example"}</summary>
                  <p>{example}</p>
                </details>
                <a href={feature.path}>{german ? `${title} öffnen` : `Open ${title}`}</a>
              </li>
            );
          })}
        </ul>
      </section>
    </main>
  );
}
