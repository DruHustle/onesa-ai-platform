import { useEffect, useRef, useState } from 'react';
import { Alert, ScrollView, View } from 'react-native';
import * as Crypto from 'expo-crypto';
import { z } from 'zod';
import { chatEvents } from '../../../packages/api-client/sse';
import { Client } from './client.ts';
import { agentRunsSchema, conversationListSchema, conversationSchema, detailSchema, documentsSchema, KNOWLEDGE_DOCUMENTS, KNOWLEDGE_SEARCH, messageText, modelsSchema, searchSchema, toolsSchema, tripSchema, tripsSchema, type Conversation, type Detail, type Model } from './protocol.ts';
import { Busy, Button, Copy, failure, Field, Heading, layout, Notice, Panel } from './ui';

type ScreenProps = { client: Client; active: boolean };

export function Chat({ client, active }: ScreenProps) {
  const [conversations, setConversations] = useState<Conversation[]>([]), [models, setModels] = useState<Model[]>([]);
  const [selected, setSelected] = useState<string | null>(null), [detail, setDetail] = useState<Detail | null>(null);
  const [drafts, setDrafts] = useState<Record<string, string>>({}), [partial, setPartial] = useState('');
  const [busy, setBusy] = useState(false), [loading, setLoading] = useState(true), [error, setError] = useState('');
  const controller = useRef<AbortController | null>(null), sending = useRef(false), current = useRef(selected), mounted = useRef(true);
  const run = useRef<{ conversation: string; id: string } | null>(null);
  current.current = selected;
  const key = selected || 'new', draft = drafts[key] || '';
  const refresh = async (signal?: AbortSignal) => {
    const [list, model] = await Promise.all([client.json(conversationListSchema, '/conversations?limit=100', 'GET', undefined, signal), client.json(modelsSchema, '/models', 'GET', undefined, signal)]);
    if (!signal?.aborted && mounted.current) { setConversations(list.items); setModels(model.items); }
  };
  useEffect(() => { const stop = new AbortController(); mounted.current = true; void refresh(stop.signal).catch(e => { if (!stop.signal.aborted) setError(failure(e)); }).finally(() => { if (!stop.signal.aborted) setLoading(false); }); return () => { mounted.current = false; stop.abort(); controller.current?.abort(); }; }, [client]); // The authenticated workspace remounts on account change.
  async function open(id: string | null) {
    if (sending.current) return;
    current.current = id; setSelected(id); setDetail(null); setPartial(''); setError('');
    if (!id) return;
    setLoading(true);
    try { const value = await client.json(detailSchema, `/conversations/${id}`); if (current.current === id && mounted.current) setDetail(value); }
    catch (e) { if (current.current === id && mounted.current) setError(failure(e)); }
    finally { if (current.current === id && mounted.current) setLoading(false); }
  }
  async function send() {
    if (sending.current || !active || !draft.trim()) return;
    sending.current = true; setBusy(true); setError(''); setPartial('');
    const request = new AbortController(); controller.current = request; run.current = null;
    let id = selected;
    const text = draft.trim();
    try {
      if (!id) {
        const created = await client.json(conversationSchema, '/conversations', 'POST', { title: text.slice(0, 80), selected_model_id: 'default' }, request.signal);
        id = created.id; current.current = id; setSelected(id);
        setDrafts(previous => ({ ...previous, new: '', [created.id]: text }));
      }
      const response = await client.request('/chat/completions', 'POST', { conversation_id: id, content: text, model_id: 'default', stream: true, document_ids: [] }, request.signal);
      if (!response.body) throw new Error('Streaming is unavailable. Refresh this conversation before retrying.');
      for await (const event of chatEvents(response.body)) {
        if (request.signal.aborted || !mounted.current) break;
        if (event.kind === 'message_start') { if (event.conversation_id !== id) throw new Error('Conversation response was rejected.'); run.current = { conversation: id, id: event.run_id }; }
        if (event.kind === 'content_delta') setPartial(previous => previous + event.text);
        if (event.kind === 'error') throw new Error('The response could not finish. Refresh to see its saved status before trying again.');
      }
      if (!request.signal.aborted && mounted.current) {
        const saved = await client.json(detailSchema, `/conversations/${id}`);
        setDetail(saved); setPartial(''); setDrafts(previous => ({ ...previous, [id!]: '' }));
        await refresh();
      }
    } catch (e) {
      if (!request.signal.aborted && mounted.current) setError(`${failure(e)} Refresh the conversation before sending again; your message may already be saved.`);
    } finally {
      request.abort(); controller.current = null; run.current = null; sending.current = false;
      if (mounted.current) setBusy(false);
    }
  }
  async function stop() {
    const owned = run.current, conversation = current.current; controller.current?.abort();
    const stillSelected = () => mounted.current && current.current === conversation;
    setError('Stopped receiving. Checking the saved response…');
    try {
      if (owned) await client.request(`/conversations/${owned.conversation}/cancel`, 'POST', { run_id: owned.id });
      if (conversation) {
        const saved = await client.json(detailSchema, `/conversations/${conversation}`);
        if (stillSelected()) setDetail(saved);
      }
      if (stillSelected()) { setPartial(''); setError('Stopped. The saved status is shown below; upstream work may already have completed.'); }
    } catch { if (stillSelected()) setError('Stopped receiving. The service could not confirm cancellation; refresh before sending again.'); }
  }
  return <View style={{ gap: 16 }}>
    <Heading>Chat</Heading><Copy muted>Ask, explore and return to your conversations.</Copy>
    {models.map(model => <Panel key={model.id}><Copy>{model.name}</Copy><Copy small muted>{model.real_inference ? 'Configured model' : 'Mock responses'} · {model.backend} · {model.model_identifier}</Copy></Panel>)}
    <View style={layout.row}><Button secondary disabled={busy || !active} onPress={() => void open(null)}>New conversation</Button><Button secondary disabled={busy || !active} onPress={() => void (selected ? open(selected) : refresh()).catch(e => setError(failure(e)))}>Refresh</Button></View>
    {conversations.length > 0 && <Panel><Heading level={2}>Recent conversations</Heading><ScrollView horizontal style={{ maxHeight: 64 }} contentContainerStyle={{ gap: 8 }}>{conversations.map(row => <Button key={row.id} secondary selected={row.id === selected} disabled={busy || !active} onPress={() => void open(row.id)}>{row.title}</Button>)}</ScrollView><Copy muted small>Up to 100 recent conversations. Drafts stay in memory while you use this app.</Copy></Panel>}
    {loading && <Busy />}
    <Notice message={error} error />
    {detail?.messages.filter(message => message.role !== 'system').map(message => <Panel key={message.id}><Copy muted small>{message.role === 'user' ? 'You' : 'Onesa AI'} · {message.status}</Copy><Copy>{messageText(message.content)}</Copy></Panel>)}
    {partial !== '' && <Panel><Copy muted small>Onesa AI · receiving, not yet confirmed saved</Copy><Copy>{partial}</Copy></Panel>}
    <Panel><Field label="Message" value={draft} multiline maxLength={32000} editable={!busy && active} onChangeText={value => setDrafts(previous => ({ ...previous, [key]: value }))} placeholder="What would you like to work on?" />
      {busy ? <Button secondary onPress={() => void stop()}>Stop response</Button> : <Button disabled={!active || !draft.trim()} onPress={() => void send()}>Send message</Button>}
      <Copy small muted>AI responses can be mistaken. Check facts before acting.</Copy>
    </Panel>
  </View>;
}

export function Knowledge({ client, active }: ScreenProps) {
  const [documents, setDocuments] = useState<z.infer<typeof documentsSchema>['items']>([]), [query, setQuery] = useState('');
  const [results, setResults] = useState<z.infer<typeof searchSchema> | null>(null), [busy, setBusy] = useState(false), [error, setError] = useState('');
  const pending = useRef(false), request = useRef<AbortController | null>(null);
  useEffect(() => { const signal = new AbortController(); void client.json(documentsSchema, `${KNOWLEDGE_DOCUMENTS}?limit=100`, 'GET', undefined, signal.signal).then(v => { if (!signal.signal.aborted) setDocuments(v.items); }).catch(e => { if (!signal.signal.aborted) setError(failure(e)); }); return () => { signal.abort(); request.current?.abort(); }; }, [client]);
  async function search() {
    if (pending.current || !query.trim() || !active) return;
    pending.current = true; setBusy(true); setError(''); const stop = new AbortController(); request.current = stop;
    try { const value = await client.json(searchSchema, KNOWLEDGE_SEARCH, 'POST', { query: query.trim(), document_ids: [] }, stop.signal); if (!stop.signal.aborted) setResults(value); }
    catch (e) { if (!stop.signal.aborted) setError(failure(e)); }
    finally { pending.current = false; if (!stop.signal.aborted) setBusy(false); }
  }
  return <View style={{ gap: 16 }}><Heading>Knowledge</Heading><Copy muted>Search the documents in your AI workspace.</Copy>
    <Panel><Field label="Search your documents" value={query} onChangeText={setQuery} maxLength={4000} editable={active && !busy} /><Button onPress={() => void search()} disabled={!active || busy || !query.trim()}>{busy ? 'Searching…' : 'Search'}</Button></Panel>
    <Notice message={error} error />
    {results && <Copy muted>{results.sources.length} sources · {results.backend} retrieval</Copy>}
    {results?.sources.map((source, i) => <Panel key={`${source.document_id}-${source.chunk}-${i}`}><Heading level={2}>{source.title}</Heading><Copy>{source.text}</Copy><Copy small muted>Source chunk {source.chunk} · {source.embedding_version}</Copy></Panel>)}
    <Panel><Heading level={2}>Your documents</Heading>{documents.length ? documents.map(row => <View key={row.id}><Copy>{row.title}</Copy><Copy small muted>{row.media_type} · {row.embedding_version}</Copy></View>) : <Copy muted>No documents loaded. Upload documents in the web workspace, then reopen Knowledge.</Copy>}<Copy small muted>Shows up to 100 documents. Uploads and document removal are available in the web workspace.</Copy></Panel>
  </View>;
}

export function Agents({ client, active }: ScreenProps) {
  const [runs, setRuns] = useState<z.infer<typeof agentRunsSchema>['items']>([]), [tools, setTools] = useState<z.infer<typeof toolsSchema>['items']>([]);
  const [allowed, setAllowed] = useState<string[]>([]), [goal, setGoal] = useState(''), [busy, setBusy] = useState(false), [error, setError] = useState('');
  const pending = useRef(false), request = useRef<AbortController | null>(null);
  const refresh = async (signal?: AbortSignal) => { const [history, available] = await Promise.all([client.json(agentRunsSchema, '/agents/runs?limit=50', 'GET', undefined, signal), client.json(toolsSchema, '/agents/tools', 'GET', undefined, signal)]); if (!signal?.aborted) { setRuns(history.items); setTools(available.items.filter(tool => tool.effect === 'local computation')); } };
  useEffect(() => { const stop = new AbortController(); void refresh(stop.signal).catch(e => { if (!stop.signal.aborted) setError(failure(e)); }); return () => { stop.abort(); request.current?.abort(); }; }, [client]);
  async function run() {
    if (pending.current || !active || !goal.trim() || !allowed.length) return;
    pending.current = true; setBusy(true); setError(''); const stop = new AbortController(); request.current = stop;
    try {
      await client.json(agentRunsSchema.shape.items.element, '/agents/runs', 'POST', { id: Crypto.randomUUID(), goal: goal.trim(), allowed_tools: allowed, steps: [] }, stop.signal);
      if (!stop.signal.aborted) { setGoal(''); await refresh(stop.signal); }
    } catch (e) { if (!stop.signal.aborted) setError(`${failure(e)} Refresh history before creating another run.`); }
    finally { pending.current = false; if (!stop.signal.aborted) setBusy(false); }
  }
  return <View style={{ gap: 16 }}><Heading>Agents</Heading><Copy muted>Run a bounded task with the local tools you explicitly select.</Copy>
    <Panel><Field label="Task" value={goal} onChangeText={setGoal} multiline maxLength={4000} editable={active && !busy} />
      <Copy>Allowed tools</Copy>{tools.map(tool => <Button key={tool.name} secondary selected={allowed.includes(tool.name)} disabled={busy || !active} onPress={() => setAllowed(previous => previous.includes(tool.name) ? previous.filter(name => name !== tool.name) : [...previous, tool.name])}>{`${allowed.includes(tool.name) ? '✓ ' : ''}${tool.name}`}</Button>)}
      {!tools.length && <Copy muted>No local tools are available.</Copy>}
      <Button disabled={busy || !active || !allowed.length || !goal.trim()} onPress={() => Alert.alert('Run this task?', `Allow these local tools: ${allowed.join(', ')}.`, [{ text: 'Cancel', style: 'cancel' }, { text: 'Run task', onPress: () => void run() }])}>{busy ? 'Running…' : 'Review and run'}</Button><Copy small muted>No machine control, external messages or bookings are available here.</Copy>
    </Panel><Notice message={error} error /><Button secondary disabled={busy || !active} onPress={() => void refresh().catch(e => setError(failure(e)))}>Refresh history</Button>
    {runs.map(row => <Panel key={row.id}><Heading level={2}>{row.goal}</Heading><Copy muted>{row.status}</Copy>{row.steps.map((step, i) => <Copy key={i}>{JSON.stringify(step, null, 2)}</Copy>)}</Panel>)}
  </View>;
}

export function Travel({ client, active }: ScreenProps) {
  const [trips, setTrips] = useState<z.infer<typeof tripsSchema>['items']>([]), [selected, setSelected] = useState<z.infer<typeof tripSchema> | null>(null);
  const [destination, setDestination] = useState(''), [duration, setDuration] = useState('3'), [budget, setBudget] = useState(''), [currency, setCurrency] = useState('EUR'), [preferences, setPreferences] = useState('');
  const [busy, setBusy] = useState(false), [error, setError] = useState(''); const pending = useRef(false), request = useRef<AbortController | null>(null);
  const refresh = async (signal?: AbortSignal) => { const value = await client.json(tripsSchema, '/travel/trips?limit=50', 'GET', undefined, signal); if (!signal?.aborted) setTrips(value.items); };
  useEffect(() => { const stop = new AbortController(); void refresh(stop.signal).catch(e => { if (!stop.signal.aborted) setError(failure(e)); }); return () => { stop.abort(); request.current?.abort(); }; }, [client]);
  async function plan() {
    if (pending.current || !active) return;
    const days = Number(duration), amount = Number(budget);
    if (!destination.trim() || !Number.isInteger(days) || days < 1 || days > 14 || !Number.isFinite(amount) || amount <= 0 || amount > 100000000 || !/^[A-Z]{3}$/.test(currency)) { setError('Enter a destination, 1–14 days, a positive budget and a three-letter currency.'); return; }
    pending.current = true; setBusy(true); setError(''); const stop = new AbortController(); request.current = stop;
    try { const trip = await client.json(tripSchema, '/travel/trips', 'POST', { destination: destination.trim(), duration: days, budget: amount, currency, preferences }, stop.signal); if (!stop.signal.aborted) { setSelected(trip); await refresh(stop.signal); } }
    catch (e) { if (!stop.signal.aborted) setError(`${failure(e)} Check saved trips before submitting again.`); }
    finally { pending.current = false; if (!stop.signal.aborted) setBusy(false); }
  }
  return <View style={{ gap: 16 }}><Heading>Travel</Heading><Copy muted>Plan an itinerary and keep it with your workspace.</Copy><Panel><Copy>Suggestions only. Prices, availability and bookings are not verified.</Copy>
    <Field label="Destination" value={destination} onChangeText={setDestination} maxLength={200} editable={active && !busy} /><Field label="Days (1–14)" value={duration} onChangeText={setDuration} keyboardType="number-pad" maxLength={2} editable={active && !busy} /><Field label="Budget" value={budget} onChangeText={setBudget} keyboardType="decimal-pad" maxLength={12} editable={active && !busy} /><Field label="Currency" value={currency} onChangeText={value => setCurrency(value.toUpperCase())} maxLength={3} autoCapitalize="characters" editable={active && !busy} /><Field label="Preferences" value={preferences} onChangeText={setPreferences} multiline maxLength={4000} editable={active && !busy} /><Button disabled={!active || busy} onPress={() => void plan()}>{busy ? 'Planning…' : 'Create itinerary'}</Button>
    </Panel><Notice message={error} error /><Panel><Heading level={2}>Saved trips</Heading><Button secondary disabled={busy || !active} onPress={() => void refresh().catch(e => setError(failure(e)))}>Refresh trips</Button>{trips.map(trip => <Button key={trip.id} secondary selected={selected?.id === trip.id} disabled={busy} onPress={() => setSelected(trip)}>{`${trip.destination} · ${trip.duration} days`}</Button>)}</Panel>
    {selected && <Panel><Heading level={2}>{selected.destination}</Heading><Copy muted>{selected.itinerary.backend === 'mock' ? 'Mock itinerary' : `Generated with ${selected.itinerary.backend}`} · revision {selected.revision}</Copy><Copy>{selected.notice}</Copy>{selected.itinerary.days.map(day => <View key={day.day} style={{ gap: 8 }}><Heading level={2}>Day {day.day}</Heading>{day.activities.map((item, i) => <View key={i}><Copy>{item.title}</Copy><Copy muted>{item.notes}</Copy></View>)}</View>)}{selected.itinerary.assumptions.map((value, i) => <Copy key={i} muted>{value}</Copy>)}</Panel>}
  </View>;
}
