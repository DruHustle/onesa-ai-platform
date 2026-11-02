import "server-only";
import { proxy } from "../backend";
import { parseIdentityMethod, type OnesaMethod } from "../identity-method";

/** Render the real sign-in method without forwarding any browser credentials. */
export async function loadIdentityMethod(): Promise<OnesaMethod> {
  try {
    const response = await proxy(new Request("http://localhost/api/v1/auth/onesa/config", {
      signal: AbortSignal.timeout(1500),
    }));
    if (response.status === 404) return { enabled: false, account_url: null };
    if (!response.ok) throw new Error("Sign-in configuration unavailable");
    return parseIdentityMethod(await response.json());
  } catch {
    return { enabled: false, account_url: null, unavailable: true };
  }
}
