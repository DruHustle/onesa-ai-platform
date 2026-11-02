/** Public presentation capability only; the API still authorizes every request. */
export type OnesaMethod = {
  enabled: boolean;
  account_url: string | null;
  unavailable?: boolean;
  pending?: boolean;
};

export function parseIdentityMethod(value: unknown): OnesaMethod {
  if (!value || typeof value !== "object") throw new Error("Invalid sign-in configuration");
  const method = value as Record<string, unknown>;
  if (typeof method.enabled !== "boolean" ||
      (method.account_url !== null && typeof method.account_url !== "string"))
    throw new Error("Invalid sign-in configuration");
  if (method.enabled) {
    if (typeof method.account_url !== "string") throw new Error("Missing account destination");
    const url = new URL(method.account_url);
    if (url.username || url.password || (url.protocol !== "https:" &&
        !(url.protocol === "http:" && ["localhost", "127.0.0.1", "[::1]"].includes(url.hostname))))
      throw new Error("Invalid account destination");
  }
  return { enabled: method.enabled, account_url: method.enabled ? method.account_url as string : null };
}
