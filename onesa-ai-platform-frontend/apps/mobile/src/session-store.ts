import { validCredential, type Credential } from './protocol.ts';

export interface SessionStorage {
  read(): Promise<string | null>;
  write(value: string): Promise<void>;
  remove(): Promise<void>;
}

// Native keychain operations can finish out of order. Keep reads, validation,
// expiry deletion and new sign-in writes in the order the app requested them.
export class SessionStore {
  private pending: Promise<void> = Promise.resolve();
  private readonly storage: SessionStorage;
  constructor(storage: SessionStorage) { this.storage = storage; }

  private ordered<T>(operation: () => Promise<T>): Promise<T> {
    const result = this.pending.then(operation);
    this.pending = result.then(() => {}, () => {});
    return result;
  }

  restore(): Promise<Credential | null> {
    return this.ordered(async () => {
      const raw = await this.storage.read();
      if (!raw) return null;
      try { return validCredential(JSON.parse(raw)); }
      catch { await this.storage.remove(); return null; }
    });
  }

  save(credential: Credential): Promise<void> {
    return this.ordered(async () => {
      await this.storage.write(JSON.stringify(validCredential(credential)));
    });
  }

  clear(): Promise<void> { return this.ordered(() => this.storage.remove()); }
}
