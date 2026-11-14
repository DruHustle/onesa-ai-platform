"use client";
import type { Component, Model } from "../lib/twins";
import {
  DEFAULT_INSPECTION,
  type InspectionControls,
} from "../lib/twin-viewer-contract";

export default function TwinInspectionControls({
  model,
  components,
  selected,
  value,
  onChange,
  hideCovers,
  restore,
}: {
  model: Model;
  components: Component[];
  selected: string;
  value: InspectionControls;
  onChange: (value: InspectionControls) => void;
  hideCovers: () => void;
  restore: () => void;
}) {
  const authored = model.definition.inspection;
  const change = (patch: Partial<InspectionControls>) =>
    onChange({ ...value, ...patch });
  return (
    <details>
      <summary>Section, subassembly and reveal controls</summary>
      {authored ? (
        <>
          <p>
            Illustrative mechanical reference. Explosion shows authored part
            separation; it is not a validated maintenance sequence.
          </p>
          <div className="twin-inspection-controls">
            <label>
              Explosion scope
              <select
                aria-label="Explosion scope"
                value={value.scope || ""}
                onChange={(e) => change({ scope: e.target.value || null })}
              >
                <option value="">Whole assembly</option>
                {components
                  .filter((c) => c.renderable === false)
                  .map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name}
                    </option>
                  ))}
              </select>
            </label>
            <button
              disabled={
                !components.some(
                  (c) => c.id === selected && c.renderable === false,
                )
              }
              onClick={() => change({ scope: selected, explode: 1 })}
            >
              Explode selected subassembly
            </button>
            <label>
              <input
                type="checkbox"
                checked={value.guides}
                onChange={(e) => change({ guides: e.target.checked })}
              />
              Guide lines
            </label>
            <label>
              <input
                type="checkbox"
                checked={value.labels}
                onChange={(e) => change({ labels: e.target.checked })}
              />
              Part labels
            </label>
          </div>
        </>
      ) : (
        <p>
          This imported model has no reviewed explosion choreography or
          solid-cap metadata. Sectioning reveals only its supplied surfaces.
        </p>
      )}
      <div className="twin-inspection-controls">
        <label>
          <input
            type="checkbox"
            checked={value.section_enabled}
            onChange={(e) => change({ section_enabled: e.target.checked })}
          />
          Section plane
        </label>
        <label>
          Section axis
          <select
            aria-label="Section axis"
            value={value.section_axis}
            onChange={(e) =>
              change({ section_axis: e.target.value as "x" | "y" | "z" })
            }
          >
            <option value="x">X · along shaft</option>
            <option value="y">Y · horizontal cut</option>
            <option value="z">Z · longitudinal cut</option>
          </select>
        </label>
        <label>
          Section position · {Math.round(value.section_position * 100)}%
          <input
            aria-label="Section position"
            type="range"
            min="-100"
            max="100"
            value={value.section_position * 100}
            onChange={(e) =>
              change({ section_position: Number(e.target.value) / 100 })
            }
          />
        </label>
        <label>
          <input
            type="checkbox"
            checked={value.section_flip}
            onChange={(e) => change({ section_flip: e.target.checked })}
          />
          Reverse cut direction
        </label>
        <label>
          <input
            type="checkbox"
            disabled={!authored?.closed_solids.length}
            checked={value.section_caps}
            onChange={(e) => change({ section_caps: e.target.checked })}
          />
          Solid cut faces
        </label>
        <button
          onClick={() =>
            change({
              section_enabled: false,
              section_axis: "x",
              section_position: 0,
              section_flip: false,
            })
          }
        >
          Reset section
        </button>
        {authored && (
          <>
            <label>
              <input
                type="checkbox"
                checked={value.ghost_housings}
                onChange={(e) => change({ ghost_housings: e.target.checked })}
              />
              Ghost housings
            </label>
            <button onClick={hideCovers}>Hide covers</button>
          </>
        )}
        <button
          onClick={() => {
            onChange({ ...DEFAULT_INSPECTION });
            restore();
          }}
        >
          Restore all
        </button>
      </div>
      {authored && (
        <details>
          <summary>Reference scope and simplifications</summary>
          <p>{authored.description}</p>
          <ul>
            {authored.scope_notes.map((note) => (
              <li key={note}>{note}</li>
            ))}
          </ul>
          {authored.unavailable.length > 0 && (
            <p>Unavailable: {authored.unavailable.join("; ")}</p>
          )}
        </details>
      )}
    </details>
  );
}

export function TwinExplosionControls({
  value,
  onChange,
}: {
  value: InspectionControls;
  onChange: (value: InspectionControls) => void;
}) {
  return (
    <div className="twin-explosion-controls">
      <button
        onClick={() =>
          onChange({ ...value, explode: value.explode > 0 ? 0 : 1 })
        }
      >
        {value.explode > 0 ? "Reassemble" : "Explode"}
      </button>
      <label>
        Explosion · {Math.round(value.explode * 100)}%
        <input
          aria-label="Explosion percent"
          type="range"
          min="0"
          max="100"
          value={value.explode * 100}
          onChange={(e) =>
            onChange({ ...value, explode: Number(e.target.value) / 100 })
          }
        />
      </label>
      <span>Illustrative reference</span>
    </div>
  );
}
