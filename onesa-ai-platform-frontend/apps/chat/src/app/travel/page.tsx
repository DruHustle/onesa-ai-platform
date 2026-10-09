"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import FeatureShell from "../../components/feature-shell";
import { call } from "../../lib/api";
type Trip = {
  id: string;
  destination: string;
  duration: number;
  budget: number;
  currency: string;
  preferences: string;
  revision: number;
  notice: string;
  itinerary: {
    days: { day: number; activities: { title: string; notes: string }[] }[];
    assumptions: string[];
    backend: string;
  };
};
export default function Travel() {
  const [trips, setTrips] = useState<Trip[]>([]),
    [selected, setSelected] = useState<Trip | null>(null),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  useEffect(() => {
    call("/travel/trips")
      .then((r) => r.json())
      .then((r) => setTrips(r.items))
      .catch((e) => setError(e.message));
  }, []);
  async function save(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const form = new FormData(event.currentTarget);
    const body = {
      destination: form.get("destination"),
      duration: Number(form.get("duration")),
      budget: Number(form.get("budget")),
      currency: form.get("currency"),
      preferences: form.get("preferences"),
      ...(selected ? { expected_revision: selected.revision } : {}),
    };
    try {
      const r = await call(
        selected ? `/travel/trips/${selected.id}` : "/travel/trips",
        selected ? "PUT" : "POST",
        body,
      );
      setSelected(await r.json());
      const list = await call("/travel/trips");
      setTrips((await list.json()).items);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function remove() {
    if (!selected || !window.confirm("Delete this trip?")) return;
    try {
      await call(`/travel/trips/${selected.id}`, "DELETE");
      setTrips((p) => p.filter((t) => t.id !== selected.id));
      setSelected(null);
    } catch (e) {
      setError((e as Error).message);
    }
  }
  return (
    <FeatureShell title="Plan your next journey">
      <p className="intro">
        Explore ideas, save a plan, and refine it as you go. Suggestions require
        independent checks before you travel.
      </p>
      {error && (
        <div className="error" role="alert">
          {error} <Link href="/">Return to Chat to sign in.</Link>
        </div>
      )}
      <div className="travel-grid">
        <aside>
          <button disabled={busy} onClick={() => setSelected(null)}>
            ＋ New trip
          </button>
          {trips.map((t) => (
            <button
              disabled={busy}
              className="trip-link"
              key={t.id}
              onClick={() => setSelected(t)}
            >
              {t.destination} · {t.duration} days
            </button>
          ))}
        </aside>
        <div>
          <form
            className="feature-card"
            onSubmit={save}
            key={`${selected?.id || "new"}:${selected?.revision || 0}`}
          >
            <label>
              Destination
              <input
                name="destination"
                required
                maxLength={200}
                defaultValue={selected?.destination}
              />
            </label>
            <div className="form-row">
              <label>
                Days
                <input
                  name="duration"
                  type="number"
                  min={1}
                  max={14}
                  required
                  defaultValue={selected?.duration || 3}
                />
              </label>
              <label>
                Total budget
                <input
                  name="budget"
                  type="number"
                  min={1}
                  max={100000000}
                  required
                  defaultValue={selected?.budget || 500}
                />
              </label>
              <label>
                Currency
                <input
                  name="currency"
                  pattern="[A-Z]{3}"
                  maxLength={3}
                  required
                  defaultValue={selected?.currency || "USD"}
                />
              </label>
            </div>
            <label>
              Interests and preferences
              <textarea
                name="preferences"
                maxLength={4000}
                defaultValue={selected?.preferences}
                placeholder="Nature, museums, a relaxed pace…"
              />
            </label>
            <button className="send" disabled={busy}>
              {busy ? "Planning…" : selected ? "Revise plan" : "Create plan"}
            </button>
          </form>
          {selected && (
            <section>
              <div className="notice">
                {selected.notice}{" "}
                {selected.itinerary.backend === "mock" &&
                  "This is a mock itinerary."}
              </div>
              <h2>
                {selected.destination} · revision {selected.revision}
              </h2>
              {selected.itinerary.days.map((day) => (
                <article className="feature-card" key={day.day}>
                  <p className="eyebrow">DAY {day.day}</p>
                  {day.activities.map((activity, i) => (
                    <div key={i}>
                      <h3>{activity.title}</h3>
                      <p>{activity.notes}</p>
                    </div>
                  ))}
                </article>
              ))}
              <h3>Planning assumptions</h3>
              <ul>
                {selected.itinerary.assumptions.map((a, i) => (
                  <li key={i}>{a}</li>
                ))}
              </ul>
              <button onClick={remove} disabled={busy}>
                Delete trip
              </button>
            </section>
          )}
        </div>
      </div>
    </FeatureShell>
  );
}
