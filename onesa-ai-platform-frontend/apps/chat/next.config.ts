import type { NextConfig } from "next";
import path from "node:path";
const config: NextConfig = {
  agentRules: false, // Keep agent instructions in the repository-root AGENTS.md.
  output: "standalone",
  outputFileTracingRoot: path.join(__dirname, "../.."),
  compress: false, // Keep SSE deltas visible immediately rather than buffering gzip output.
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "same-origin" },
          { key: "X-Frame-Options", value: "DENY" },
          {
            key: "Permissions-Policy",
            value: "camera=(), microphone=(), geolocation=()",
          },
        ],
      },
    ];
  },
};
export default config;
