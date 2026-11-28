import * as Crypto from 'expo-crypto';
import * as SecureStore from 'expo-secure-store';
import * as WebBrowser from 'expo-web-browser';
import { Platform } from 'react-native';
import { z } from 'zod';
import { Client } from './client.ts';
import { authorization, CALLBACK, callbackCode, credentialSchema, validCredential, type Credential } from './protocol.ts';
import { SessionStore } from './session-store.ts';

const SESSION_KEY = 'onesa.ai.native.session.v1';
const options: SecureStore.SecureStoreOptions = { keychainService: 'eu.onesa.aiplatform', keychainAccessible: SecureStore.WHEN_UNLOCKED_THIS_DEVICE_ONLY };
const sessions = new SessionStore({
  read: () => SecureStore.getItemAsync(SESSION_KEY, options),
  write: value => SecureStore.setItemAsync(SESSION_KEY, value, options),
  remove: () => SecureStore.deleteItemAsync(SESSION_KEY, options),
});
const token = () => Array.from(Crypto.getRandomBytes(32), byte => byte.toString(16).padStart(2, '0')).join('');
let signingIn = false;

export function restoreSession(): Promise<Credential | null> { return sessions.restore(); }
export function clearSession(): Promise<void> { return sessions.clear(); }

export async function signIn(client: Client): Promise<Credential | null> {
  if (signingIn) throw new Error('Sign-in is already open.');
  signingIn = true;
  // PKCE verifier/state are memory-only and discarded after cancel, failure or
  // completion. A cold-start callback cannot redeem an abandoned transaction.
  const verifier = token(), state = token();
  try {
    const challenge = (await Crypto.digestStringAsync(Crypto.CryptoDigestAlgorithm.SHA256, verifier, { encoding: Crypto.CryptoEncoding.BASE64 })).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
    if (Platform.OS !== 'ios' && Platform.OS !== 'android') throw new Error('Use an installed iOS or Android build.');
    const started = authorization(await client.json(z.unknown(), '/auth/native/start', 'POST', { code_challenge: challenge, state, platform: Platform.OS }));
    const result = await WebBrowser.openAuthSessionAsync(started.authorize_url, CALLBACK);
    if (result.type !== 'success') return null;
    const code = callbackCode(result.url, state);
    const credential = validCredential(await client.json(credentialSchema, '/auth/native/token', 'POST', { code, code_verifier: verifier }));
    await sessions.save(credential);
    return credential;
  } finally { signingIn = false; }
}
