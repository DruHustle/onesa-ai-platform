"use client";
import { useEffect, useRef, useState } from "react";
import {useRecordPage, RecordPageControls, useRecordSelection} from "../../lib/record-page";
import RequireSession from "../../components/require-session";
import { useDraftNavigation } from "../../components/draft-navigation";
import FeatureShell from "../../components/feature-shell";
import { api, type TripOut as Trip } from "../../lib/api";
type Draft = {
  destination: string;
  duration: string;
  budget: string;
  currency: string;
  preferences: string;
};
const fields = (trip: Trip | null): Draft => ({
  destination: trip?.destination || "",
  duration: String(trip?.duration ?? 3),
  budget: String(trip?.budget ?? 500),
  currency: trip?.currency || "USD",
  preferences: trip?.preferences || "",
});
export default function Travel() {
  return (
    <RequireSession destination="/travel" title="Plan your next journey">
      <TravelWorkspace />
    </RequireSession>
  );
}
function TravelWorkspace() {
  const [selectedLocation, setSelectedLocation] = useRecordSelection("trip");
  const loadedLocation = useRef<string | null>(null);
  const [detailAttempt, setDetailAttempt] = useState(0);
  const [detailError, setDetailError] = useState("");
  const page = useRecordPage<Trip>("/travel/trips");
  const {items: trips, setItems: setTrips} = page;
  const
    [selected, setSelected] = useState<Trip | null>(null),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  const [draft, setDraft] = useState<Draft>(() => fields(null));
  const [baseline, setBaseline] = useState<Draft>(() => fields(null));
  const pending = useRef(false);
  const loadingTrip = Boolean(selectedLocation && selectedLocation !== selected?.id && !detailError);
  useEffect(() => {
    if (loadedLocation.current === selectedLocation) return;
    const controller = new AbortController();
    const signal = AbortSignal.any([controller.signal, AbortSignal.timeout(8000)]);
    const request = selectedLocation
      ? api("GET /travel/trips/{identifier}", {params: {identifier: selectedLocation}, signal})
      : Promise.resolve(null);
    request
      .then(trip => {
        if (signal.aborted) return;
        loadedLocation.current = trip?.id || null;
        setSelected(trip);
        setBaseline(fields(trip));
        setDraft(fields(trip));
        setDetailError("");
      })
      .catch(() => {
        if (!controller.signal.aborted) setDetailError("The saved trip is unavailable. Retry or choose another trip.");
      });
    return () => controller.abort();
  }, [selectedLocation, detailAttempt]);
  const navigate = useDraftNavigation(
    JSON.stringify(draft) !== JSON.stringify(baseline),
    busy || loadingTrip,
    () => setDraft({ ...baseline }),
  );
  function choose(trip: Trip | null) {
    navigate(() => {
      const next = fields(trip);
      setBaseline(next);
      setDraft(next);
      setSelected(trip);
      loadedLocation.current = trip?.id || null;
      setSelectedLocation(trip?.id || null);
      setDetailError("");
      setError("");
    });
  }
  function change(name: keyof Draft, value: string) {
    setDraft((previous) => ({ ...previous, [name]: value }));
  }
  async function save(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending.current || loadingTrip || detailError) return;
    pending.current = true;
    setBusy(true);
    setError("");
    const body = {
      destination: draft.destination,
      duration: Number(draft.duration),
      budget: Number(draft.budget),
      currency: draft.currency,
      preferences: draft.preferences,
      ...(selected ? { expected_revision: selected.revision } : {}),
    };
    try {
      const r = selected
        ? await api("PUT /travel/trips/{identifier}", {
            params: { identifier: selected.id },
            body: { ...body, expected_revision: selected.revision },
          })
        : await api("POST /travel/trips", { body });
      const saved = fields(r);
      setBaseline(saved);
      setDraft(saved);
      setSelected(r);
      loadedLocation.current = r.id;
      setSelectedLocation(r.id);
      setTrips((previous) => [
        r,
        ...previous.filter((trip) => trip.id !== r.id),
      ]);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      pending.current = false;
      setBusy(false);
    }
  }
  async function remove() {
    if (!selected || pending.current || !window.confirm("Delete this trip?"))
      return;
    navigate(() => {
      void deleteSelected(selected);
    });
  }
  async function deleteSelected(trip: Trip) {
    pending.current = true;
    setBusy(true);
    setError("");
    try {
      await api("DELETE /travel/trips/{identifier}", {
        params: { identifier: trip.id },
      });
      setTrips((p) => p.filter((t) => t.id !== trip.id));
      const next = fields(null);
      setBaseline(next);
      setDraft(next);
      setSelected(null);
      loadedLocation.current = null;
      setSelectedLocation(null);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      pending.current = false;
      setBusy(false);
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
          {error} Your entries are kept. Review the result before trying again.
        </div>
      )}
      {loadingTrip && <p role="status">Loading saved trip…</p>}
      {detailError && <p role="alert">{detailError} <button onClick={() => {setDetailError(""); setDetailAttempt(value => value + 1);}}>Retry saved trip</button></p>}
      <div className="travel-grid">
        <nav aria-label="Saved trips">
          <button disabled={busy || loadingTrip} onClick={() => choose(null)}>
            ＋ New trip
          </button>
          <RecordPageControls page={page} />
      {trips.map((t) => (
            <button
              disabled={busy || loadingTrip}
              className="trip-link"
              key={t.id}
              onClick={() => choose(t)}
            >
              {t.destination} · {t.duration} days
            </button>
          ))}
        </nav>
        <div>
          <form className="feature-card" onSubmit={save} aria-busy={busy}>
            <fieldset disabled={busy || loadingTrip || Boolean(detailError)} className="travel-fields">
              <label>
                Destination
                <input
                  name="destination"
                  required
                  maxLength={200}
                  value={draft.destination}
                  onChange={(event) =>
                    change("destination", event.target.value)
                  }
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
                    value={draft.duration}
                    onChange={(event) => change("duration", event.target.value)}
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
                    value={draft.budget}
                    onChange={(event) => change("budget", event.target.value)}
                  />
                </label>
                <label>
                  Currency
                  <input
                    name="currency"
                    pattern="[A-Z]{3}"
                    maxLength={3}
                    required
                    value={draft.currency}
                    onChange={(event) => change("currency", event.target.value)}
                  />
                </label>
              </div>
              <label>
                Interests and preferences
                <textarea
                  name="preferences"
                  maxLength={4000}
                  value={draft.preferences}
                  onChange={(event) =>
                    change("preferences", event.target.value)
                  }
                  placeholder="Nature, museums, a relaxed pace…"
                />
              </label>
              <button className="send" disabled={busy}>
                {busy ? "Planning…" : selected ? "Revise plan" : "Create plan"}
              </button>
            </fieldset>
          </form>
          {selected && selected.id === selectedLocation && (
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
