"use client";

import dynamic from "next/dynamic";
import Image from "next/image";
import { useEffect, useState } from "react";
import { twin, type Component, type ReferenceAsset } from "../lib/twins";
import styles from "./twin-reference-library.module.css";

const Viewer = dynamic(() => import("./twin-viewer"), {
  ssr: false,
  loading: () => <p role="status">Preparing reference preview…</p>,
});
const ignore = () => {};
const noComponents: Component[] = [];
const noIds: string[] = [];

export default function TwinReferenceLibrary({
  busy,
  canImport,
  onImport,
}: {
  busy: boolean;
  canImport: boolean;
  onImport: (id: string) => void;
}) {
  const [assets, setAssets] = useState<ReferenceAsset[]>([]);
  const [selected, setSelected] = useState("");
  const [error, setError] = useState("");
  const [retry, setRetry] = useState(0);
  const [viewerRetry, setViewerRetry] = useState(0);
  const [focus, setFocus] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    twin<{ assets: ReferenceAsset[] }>(
      "/references",
      "GET",
      undefined,
      AbortSignal.any([controller.signal, AbortSignal.timeout(15000)]),
    )
      .then((result) => {
        if (controller.signal.aborted) return;
        setAssets(result.assets);
        setSelected((value) =>
          result.assets.some((asset) => asset.id === value)
            ? value
            : result.assets[0]?.id || "",
        );
        setError("");
      })
      .catch(() => {
        if (!controller.signal.aborted)
          setError(
            "The reference library is unavailable. Your equipment remains available.",
          );
      });
    return () => controller.abort();
  }, [retry]);
  const item = assets.find((asset) => asset.id === selected);
  return (
    <section
      className={styles.library}
      aria-labelledby="reference-library-title"
    >
      <header className={styles.header}>
        <div>
          <h2 id="reference-library-title">NVIDIA reference models</h2>
          <p>
            Explore a conveyor, mobile cart and warehouse rack, then add a
            private copy to your equipment workspace.
          </p>
        </div>
        <span className={styles.badge}>Visual references</span>
      </header>
      {error ? (
        <div role="alert">
          <p>{error}</p>
          <button onClick={() => setRetry((value) => value + 1)}>
            Retry reference library
          </button>
        </div>
      ) : !item ? (
        <p role="status">Loading reference library…</p>
      ) : (
        <>
          <div
            className={styles.choices}
            aria-label="Reference model selection"
          >
            {assets.map((asset) => (
              <button
                key={asset.id}
                type="button"
                aria-pressed={item.id === asset.id}
                onClick={() => {
                  setSelected(asset.id);
                  setViewerRetry(0);
                  setFocus(0);
                }}
              >
                <Image
                  src={`/models/nvidia/${asset.thumbnail.path}`}
                  alt=""
                  width={160}
                  height={100}
                  unoptimized
                />
                <span>{asset.name}</span>
              </button>
            ))}
          </div>
          <div className={styles.layout}>
            <div
              className={styles.preview}
              data-testid="nvidia-reference-preview"
            >
              <Viewer
                key={`${item.id}-${viewerRetry}`}
                model={item.preview_model}
                referencePath={item.glb.path}
                modelTestId="reference-model-loaded"
                components={noComponents}
                selected=""
                onSelect={ignore}
                hidden={noIds}
                isolated={null}
                transparent={false}
                focus={focus}
                camera={null}
                onCamera={ignore}
                fallback={
                  <div className={styles.fallback}>
                    <Image
                      src={`/models/nvidia/${item.thumbnail.path}`}
                      alt={`${item.name}, rendered from the same NVIDIA reference model`}
                      width={600}
                      height={360}
                      unoptimized
                    />
                    <p>
                      3D is unavailable. This image shows the same model; its
                      details and import action remain available.
                    </p>
                  </div>
                }
              />
            </div>
            <div className={styles.details}>
              <h3>{item.name}</h3>
              <p>{item.attribution}</p>
              <p>
                Import adds geometry and provenance to your private workspace.
                It creates no sensor readings or device connections.
              </p>
              <p>
                Physical behaviour, collision accuracy and robot articulation
                have not been validated.
              </p>
              <div className={styles.actions}>
                <button
                  disabled={busy || !canImport}
                  onClick={() => onImport(item.id)}
                >
                  {busy ? "Adding reference…" : "Add to my workspace"}
                </button>
                <button
                  onClick={() => setFocus((value) => Math.min(value, 0) - 1)}
                >
                  Fit reference view
                </button>
                <button onClick={() => setViewerRetry((value) => value + 1)}>
                  Reload 3D preview
                </button>
              </div>
              {!canImport && (
                <p>Private model storage must be ready before importing.</p>
              )}
              <div className={styles.links}>
                <a
                  href={item.sourceUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  NVIDIA source
                </a>
                <a
                  href={`/models/nvidia/${item.licenseFile.path}`}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  CC BY 4.0 licence
                </a>
                <a
                  href={`/models/nvidia/${item.sourceFile.path}`}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  Conversion provenance
                </a>
              </div>
            </div>
          </div>
        </>
      )}
    </section>
  );
}
