import registry from "../../../../packages/onesa-design/onesa-applications.json";

export default function ApplicationsNav() {
  return (
    <details className="applications-menu">
      <summary>Onesa applications</summary>
      <nav aria-label="Onesa applications">
        {registry.applications.map(application => (
          <a key={application.id} href={application.href}>
            {application.label} <span aria-label="leaves this workspace">↗</span>
          </a>
        ))}
      </nav>
    </details>
  );
}
