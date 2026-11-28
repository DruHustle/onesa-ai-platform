import { useEffect, useRef, useState } from 'react';
import { Alert, Image, KeyboardAvoidingView, Platform, ScrollView, StatusBar, useColorScheme, View } from 'react-native';
import { SafeAreaProvider, SafeAreaView } from 'react-native-safe-area-context';
import { fetch } from 'expo/fetch';
import * as WebBrowser from 'expo-web-browser';
import { clearSession, restoreSession, signIn } from './src/auth';
import { Client, type Fetch } from './src/client';
import { ORIGIN, userSchema, type Credential, type User } from './src/protocol';
import { Agents, Chat, Knowledge, Travel } from './src/screens';
import { Busy, Button, Copy, failure, Heading, layout, Notice, palettes, Panel, Theme } from './src/ui';

type Tab = 'Chat' | 'Knowledge' | 'Agents' | 'Travel';

function Workspace({ client, user, active }: { client: Client; user: User; active: boolean }) {
  const [tab, setTab] = useState<Tab>('Chat');
  return <View style={{ gap: 20 }}><Copy muted>Workspace for {user.display_name || user.email}</Copy>
    <View accessibilityRole="tablist" style={layout.row}>{(['Chat', 'Knowledge', 'Agents', 'Travel'] as const).map(name => <Button key={name} secondary selected={name === tab} disabled={!active} onPress={() => setTab(name)}>{name}</Button>)}</View>
    {/* Keep drafts mounted across tabs. Hidden panels expose no accessibility nodes. */}
    {(['Chat', 'Knowledge', 'Agents', 'Travel'] as const).map(name => <View key={name} style={{ display: tab === name ? 'flex' : 'none' }} accessibilityElementsHidden={tab !== name} importantForAccessibility={tab === name ? 'auto' : 'no-hide-descendants'}>{name === 'Chat' ? <Chat client={client} active={active && tab === name} /> : name === 'Knowledge' ? <Knowledge client={client} active={active && tab === name} /> : name === 'Agents' ? <Agents client={client} active={active && tab === name} /> : <Travel client={client} active={active && tab === name} />}</View>)}
  </View>;
}

function Application() {
  const dark = useColorScheme() === 'dark', color = dark ? palettes.dark : palettes.light;
  const [credential, setCredential] = useState<Credential | null>(null), [owner, setOwner] = useState<User | null>(null), [busy, setBusy] = useState(true), [error, setError] = useState('');
  const locked = useRef(false), client = useRef<Client | null>(null), mounted = useRef(true);
  if (!client.current) client.current = new Client(fetch as Fetch, () => {
    client.current?.setCredential(null); setCredential(null);
    void clearSession().catch(() => setError('Device session storage could not be cleared. Close the app and try again.'));
  });
  const api = client.current;
  useEffect(() => { mounted.current = true; void (async () => {
    try { const saved = await restoreSession(); if (saved && mounted.current) { api.setCredential(saved); const user = await api.json(userSchema, '/auth/me'); if (user.id !== saved.user.id) throw new Error('The stored account did not match the service. Sign in again.'); if (mounted.current) { setOwner(user); setCredential(saved); } } }
    catch (e) { api.setCredential(null); await clearSession().catch(() => {}); if (mounted.current) setError(failure(e)); }
    finally { if (mounted.current) setBusy(false); }
  })(); return () => { mounted.current = false; api.setCredential(null); }; }, [api]);
  async function connect() {
    if (locked.current) return; locked.current = true; setBusy(true); setError('');
    try { const saved = await signIn(api); if (saved && mounted.current) { api.setCredential(saved); const user = await api.json(userSchema, '/auth/me'); if (user.id !== saved.user.id) throw new Error('The signed-in account could not be verified.'); setOwner(user); setCredential(saved); } }
    catch (e) { api.setCredential(null); setCredential(null); await clearSession().catch(() => {}); setError(failure(e)); }
    finally { locked.current = false; if (mounted.current) setBusy(false); }
  }
  async function disconnect() {
    if (locked.current) return; locked.current = true; setBusy(true); setError('');
    try { await api.request('/auth/native/logout', 'POST'); }
    catch { setError('The app is locked. The service could not confirm revocation; use account session controls before returning a lost device.'); }
    finally { api.setCredential(null); setCredential(null); setOwner(null); await clearSession().catch(() => setError('Device session storage could not be cleared. Close the app and try again.')); locked.current = false; setBusy(false); }
  }
  return <Theme.Provider value={color}><SafeAreaView style={[layout.page, { backgroundColor: color.background }]}><StatusBar barStyle={dark ? 'light-content' : 'dark-content'} /><KeyboardAvoidingView style={layout.page} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
    <ScrollView contentContainerStyle={layout.content} keyboardShouldPersistTaps="handled">
      <View style={layout.row}><Image source={require('./assets/icon.png')} accessibilityLabel="Onesa AI Platform" style={{ width: 44, height: 44, borderRadius: 12 }} /><View style={{ flex: 1, minWidth: 200 }}><Heading>Onesa AI Platform</Heading><Copy muted small>Your workspace, wherever you are</Copy></View></View>
      <Notice message={error} error />
      {busy && <Busy label="Checking your session…" />}
      {!credential && !busy && <Panel><Heading level={2}>{owner ? 'Sign in to resume' : 'Welcome to your AI workspace'}</Heading><Copy>Use your Onesa account for Chat, Knowledge, Agents and Travel.</Copy><Button onPress={() => void connect()}>Continue with Onesa</Button><Copy small muted>Sign-in opens your system browser. This app never asks for your password.</Copy><Button secondary onPress={() => void WebBrowser.openBrowserAsync(ORIGIN)}>Open web workspace</Button></Panel>}
      {credential && <View style={layout.row}><Copy muted>{credential.user.email}</Copy><Button secondary disabled={busy} onPress={() => Alert.alert('Sign out of this app?', 'Unsaved drafts will be removed from this device. Your other Onesa sessions will remain signed in.', [{ text: 'Cancel', style: 'cancel' }, { text: 'Sign out', style: 'destructive', onPress: () => void disconnect() }])}>Sign out</Button></View>}
      {owner && <View style={{ display: credential ? 'flex' : 'none' }} accessibilityElementsHidden={!credential} importantForAccessibility={credential ? 'auto' : 'no-hide-descendants'}><Workspace key={owner.id} client={api} user={owner} active={!!credential && !busy} /></View>}
    </ScrollView>
  </KeyboardAvoidingView></SafeAreaView></Theme.Provider>;
}
export default function App() { return <SafeAreaProvider><Application /></SafeAreaProvider>; }
