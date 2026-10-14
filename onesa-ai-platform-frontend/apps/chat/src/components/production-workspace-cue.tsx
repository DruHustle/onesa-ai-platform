"use client";

import { useEffect, useState } from "react";
import { api } from "../lib/api";

export default function ProductionWorkspaceCue({
  authenticated = false,
}: {
  authenticated?: boolean;
}) {
  const [confirmed, setConfirmed] = useState(false);
  useEffect(() => {
    if (
      authenticated ||
      document.documentElement.dataset.onesaEnvironment !== "production"
    )
      return;
    const controller = new AbortController();
    const signal = AbortSignal.any([
      controller.signal,
      AbortSignal.timeout(8000),
    ]);
    api("GET /auth/me", { signal })
      .then((user) => {
        if (!signal.aborted) setConfirmed(Boolean(user.id));
      })
      .catch(() => {});
    return () => controller.abort();
  }, [authenticated]);
  return authenticated || confirmed ? (
    <small className="eyebrow production-workspace-cue" role="note">
      PRODUCTION
    </small>
  ) : null;
}
