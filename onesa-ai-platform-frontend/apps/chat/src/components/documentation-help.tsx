"use client";
import { documentationRoutes, documentationUrls } from "../lib/documentation";
export default function DocumentationHelp({
  topic,
}: {
  topic: keyof typeof documentationRoutes;
}) {
  return (
    <a
      className="documentation-help"
      href={documentationUrls.public + documentationRoutes[topic]}
      title="Open the relevant Onesa documentation"
    >
      Help and documentation ↗
    </a>
  );
}
