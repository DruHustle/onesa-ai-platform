"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import FeatureShell from "../../components/feature-shell";
import { api, type TripOut as Trip } from "../../lib/api";
export default function Travel() {
  const [trips, setTrips] = useState<Trip[]>([]),
    [selected, setSelected] = useState<Trip | null>(null),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  useEffect(() => {
    api("GET /travel/trips")
      .then((r) => setTrips(r.items))
      .catch((e) => setError(e.message));
  }, []);
  async function save(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const form = new FormData(event.currentTarget);
    const body = {
      destination: String(form.get("destination") || ""),
      duration: Number(form.get("duration")),
      budget: Number(form.get("budget")),
      currency: String(form.get("currency") || ""),
      preferences: String(form.get("preferences") || ""),
      ...(selected ? { expected_revision: selected.revision } : {}),
    };
    try {
      const r = selected
        ? await api("PUT /travel/trips/{identifier}", {
            params: { identifier: selected.id },
            body: { ...body, expected_revision: selected.revision },
          })
        : await api("POST /travel/trips", { body });
      setSelected(r);
      const list = await api("GET /travel/trips");
      setTrips(list.items);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function remove() {
    if (!selected || !window.confirm("Delete this trip?")) return;
    try {
      await api("DELETE /travel/trips/{identifier}", {
        params: { identifier: selected.id },
      });
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
