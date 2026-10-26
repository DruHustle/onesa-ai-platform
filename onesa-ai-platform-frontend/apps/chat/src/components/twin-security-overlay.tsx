"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { security } from "../lib/cybersecurity";
type Signal = {
  finding_id: string;
  rule: string;
  severity: string;
  mode: string;
  component_id: string | null;
  mapping_current: boolean;
  last_seen: string;
};
export default function TwinSecurityOverlay({
  assetId,
  onFocus,
  onHighlights,
}: {
  assetId: string;
  onFocus: (id: string) => void;
  onHighlights: (ids: string[]) => void;
}) {
  const [signals, setSignals] = useState<{
      asset: string;
      items: Signal[];
    } | null>(null),
    [show, setShow] = useState(false),
    [unavailable, setUnavailable] = useState(false),
    [highlightAsset, setHighlightAsset] = useState<string | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    security<{ items: Signal[] }>(
      `/twins/${assetId}/summary`,
      "GET",
      undefined,
      controller.signal,
    )
      .then((result) => {
        if (!controller.signal.aborted) {
          setSignals({ asset: assetId, items: result.items });
          setUnavailable(false);
        }
      })
      .catch(() => {
        if (!controller.signal.aborted) {
          setUnavailable(true);
          onHighlights([]);
        }
      });
    return () => {
      controller.abort();
      onHighlights([]);
    };
  }, [assetId, onHighlights]);
  const items = signals?.asset === assetId ? signals.items : [];
  return (
    <details
      onToggle={(event) => {
        if (event.currentTarget.open) setShow(true);
      }}
    >
      <summary>Security evidence (optional)</summary>
      {show && (
        <>
          {unavailable ? (
            <p>
              Security evidence is unavailable or disabled. Equipment inspection
              remains available.
            </p>
          ) : (
            <>
              <p>
                Reviewed associations only. Process alarms and security findings
                remain separate; neither proves compromise.
              </p>
              <label>
                <input
                  type="checkbox"
                  checked={highlightAsset === assetId}
                  onChange={(e) => {
                    setHighlightAsset(e.target.checked ? assetId : null);
                    onHighlights(
                      e.target.checked
                        ? items.flatMap((s) =>
                            s.component_id ? [s.component_id] : [],
                          )
                        : [],
                    );
                  }}
                />
                Highlight mapped security components
              </label>
              {items.length ? (
                <ul>
                  {items.map((s) => (
                    <li key={s.finding_id}>
                      <Link
                        href={`/industrial/cybersecurity?view=Findings&mode=${s.mode}&finding=${s.finding_id}`}
                      >
                        {s.rule.replaceAll("_", " ")} · {s.severity} · {s.mode}
                      </Link>
                      {s.component_id && s.mapping_current ? (
                        <button onClick={() => onFocus(s.component_id!)}>
                          Focus mapped component
                        </button>
                      ) : (
                        <span> · No current installed-component mapping</span>
                      )}
                    </li>
                  ))}
                </ul>
              ) : (
                <p>
                  No authorized findings for this reviewed asset association.
                  Unassessed controls remain unknown.
                </p>
              )}
              <Link href="/industrial/cybersecurity">
                Open security investigations
              </Link>
            </>
          )}
        </>
      )}
    </details>
  );
}
