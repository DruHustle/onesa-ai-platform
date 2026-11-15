import React, {useEffect, useState, useRef} from 'react';
import {ActivityIndicator, Button, ScrollView, StyleSheet, Text, TextInput, View} from 'react-native';
import {SafeAreaProvider, SafeAreaView} from 'react-native-safe-area-context';
import * as Browser from 'expo-web-browser';
import * as Crypto from 'expo-crypto';
import * as SecureStore from 'expo-secure-store';
import {call, signIn, signOut} from './session.mjs';
import {clearSubmittedDraft, draftFor, moveDraft, openConversation, withDraft} from './conversation-state.mjs';

export default function App() {
  const [account, setAccount] = useState(null);
  const [csrf, setCsrf] = useState('');
  const [items, setItems] = useState([]);
  const [selected, setSelected] = useState(null);
  const [drafts, setDrafts] = useState(() => new Map());
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const active = useRef(false);
  const target = useRef(null);
  const previousAccount = useRef(null);
  const draft = draftFor(drafts, target.current);

  function editDraft(text) {
    const id = target.current;
    setDrafts(current => withDraft(current, id, text));
  }

  function clear() {
    setAccount(null); setCsrf(''); setSelected(null); setItems([]);
  }
  async function perform(action) {
    if (active.current) return;
    active.current = true; setBusy(true); setError('');
    try { await action(); }
    catch (err) { if(err.status === 401) clear(); setError(err.message); }
    finally { active.current = false; setBusy(false); }
  }
  async function refresh() {

    const result = await call('/conversations');
    setItems(result.items);
    if(target.current) setSelected(await call('/conversations/'+target.current));

  }
  async function connect(interactive) {
    const grant = interactive ? await signIn(Browser.openAuthSessionAsync, call, async () => {
      const bytes = await Crypto.getRandomBytesAsync(32);
      const verifier = Array.from(bytes, byte => byte.toString(16).padStart(2, '0')).join('');
      const digest = await Crypto.digestStringAsync(
        Crypto.CryptoDigestAlgorithm.SHA256,
        verifier,
        {encoding: Crypto.CryptoEncoding.BASE64},
      );
      const challenge = digest.replace(/\\+/g, '-').replace(/\\//g, '_').replace(/=+$/, '');
      return {verifier, challenge};
    }) : {};
    const user = await call('/auth/me');
    const key = user.id || user.name;
    if (previousAccount.current && previousAccount.current !== key) {setSelected(null);setItems([]);target.current=null; setDrafts(new Map());}
    previousAccount.current = key;
    let protection = user.csrf || grant.csrf || await SecureStore.getItemAsync('csrf');
    if (!protection) throw Error('Start a new sign-in to continue.');
    await SecureStore.setItemAsync('csrf',protection,{keychainAccessible:SecureStore.WHEN_UNLOCKED_THIS_DEVICE_ONLY});
    setAccount(user); setCsrf(protection);
    await refresh();
  }
  useEffect(() => {perform(() => connect(false));}, []);
  async function logout() {
    await signOut(csrf, () => SecureStore.deleteItemAsync('csrf'), () => {
      clear();
      setDrafts(new Map());
      target.current = null;
      previousAccount.current = null;
    });
  }

  async function open(id) {
    await openConversation(
      id,
      conversationId => call('/conversations/' + conversationId),
      (conversationId, detail) => {
        target.current = conversationId;
        setSelected(detail);
      },
    );
  }

  async function send() {
    const content = draft.trim();
    if (!content) return;
    let id = target.current;
    if (!id) {
      const conversation = await call('/conversations', {
        method: 'POST', csrf, body: {title: content.slice(0, 80)},
      });
      id = conversation.id;
      target.current = id;
      setSelected({conversation, messages: []});
      setDrafts(current => moveDraft(current, null, id));
    }
    await call('/chat/completions', {
      method: 'POST', csrf, body: {conversation_id: id, content, stream: false},
    });
    setDrafts(current => clearSubmittedDraft(current, id, draft));
    await refresh();
  }

  return <SafeAreaProvider><SafeAreaView style={styles.safe}><ScrollView keyboardShouldPersistTaps="handled" contentContainerStyle={styles.page}>
    <Text accessibilityRole="header" style={styles.title}>Onesa AI Platform</Text>
    {busy && <ActivityIndicator accessibilityLabel="Working" />}
    {!!error && <Text accessibilityRole="alert" style={styles.error}>{error}</Text>}
    {!account ? <Button title="Sign in with Onesa" disabled={busy} onPress={()=>perform(()=>connect(true))} /> : <>
      <Text style={styles.muted}>{account.display_name || account.name}</Text>

      <Text style={styles.heading}>{selected?.conversation.title || 'New conversation'}</Text>
      {selected?.messages.map(m=><View key={m.id} style={styles.item}><Text style={styles.heading}>{m.role}</Text><Text selectable>{m.content?.text || m.status}</Text></View>)}
      <TextInput multiline style={styles.input} value={draft} onChangeText={editDraft} accessibilityLabel="Message" placeholder="Message" />
      <Button title="Send message" disabled={busy || !draft.trim()} onPress={()=>perform(send)} />
      <Button title="New conversation" disabled={busy} onPress={()=>{target.current=null;setSelected(null);}} />
      <Text style={styles.heading}>Saved conversations</Text>
      {items.map(item=><Button key={item.id} title={item.title} disabled={busy} onPress={()=>perform(()=>open(item.id))}/>)}

      <Button title="Refresh" disabled={busy} onPress={()=>perform(refresh)} />
      <Button title="Sign out" disabled={busy} onPress={()=>perform(logout)} />
    </>}
  </ScrollView></SafeAreaView></SafeAreaProvider>;
}
const styles = StyleSheet.create({
  safe:{flex:1, backgroundColor:'#fff'},page:{padding:22,gap:14},title:{fontSize:30,fontWeight:'700',color:'#192739'},
  heading:{fontSize:22,fontWeight:'600',color:'#24384e'},muted:{color:'#405365'},error:{color:'#962f2b'},
  input:{borderWidth:1,borderRadius:8,padding:12,borderColor:'#607386',minHeight:54},item:{paddingVertical:10,gap:4},
});
