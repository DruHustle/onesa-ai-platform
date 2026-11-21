"use client";

import {useEffect, useRef, useState, useSyncExternalStore} from "react";

type Result = {isFinal: boolean; [index: number]: {transcript: string}};
type RecognitionEvent = {resultIndex: number; results: ArrayLike<Result>};
type BrowserRecognition = {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  maxAlternatives: number;
  onresult: ((event: RecognitionEvent) => void) | null;
  onerror: ((event: {error: string}) => void) | null;
  onend: (() => void) | null;
  start(): void;
  stop(): void;
  abort(): void;
};
type RecognitionWindow = Window & {
  SpeechRecognition?: new () => BrowserRecognition;
  webkitSpeechRecognition?: new () => BrowserRecognition;
};

const subscribeBrowserCapability = () => () => {};
const unavailableOnServer = () => false;
function canTranscribe() {
  if (typeof window === "undefined") return false;
  const browser = window as RecognitionWindow;
  return Boolean(browser.SpeechRecognition || browser.webkitSpeechRecognition);
}
function canSpeak() {
  return typeof window !== "undefined" &&
    "speechSynthesis" in window && "SpeechSynthesisUtterance" in window;
}

export function SpeechDictation({
  language, disabled, onTranscript,
}: {
  language: string;
  disabled: boolean;
  onTranscript: (text: string) => void;
}) {
  const supported = useSyncExternalStore(subscribeBrowserCapability, canTranscribe, unavailableOnServer);
  const [listening, setListening] = useState(false);
  const [notice, setNotice] = useState("");
  const recognizer = useRef<BrowserRecognition | null>(null);
  const deadline = useRef<ReturnType<typeof setTimeout> | null>(null);
  const delivered = useRef(new Set<number>());

  useEffect(() => {
    return () => {
      if (deadline.current) clearTimeout(deadline.current);
      recognizer.current?.abort();
      recognizer.current = null;
    };
  }, []);
  useEffect(() => {
    if (disabled && recognizer.current) recognizer.current.abort();
  }, [disabled]);

  function stop() {
    recognizer.current?.stop();
    setNotice("Finishing dictation…");
  }
  function start() {
    if (disabled || recognizer.current) return;
    const speech = window as RecognitionWindow;
    const Recognition = speech.SpeechRecognition || speech.webkitSpeechRecognition;
    if (!Recognition) {
      setNotice("Speech recognition is unavailable in this browser.");
      return;
    }
    const current = new Recognition();
    current.lang = language;
    current.continuous = false;
    current.interimResults = false;
    current.maxAlternatives = 1;
    delivered.current.clear();
    current.onresult = event => {
      if (recognizer.current !== current) return;
      const words: string[] = [];
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const result = event.results[i];
        if (result.isFinal && !delivered.current.has(i)) {
          delivered.current.add(i);
          const sentence = result[0]?.transcript?.trim();
          if (sentence) words.push(sentence);
        }
      }
      if (words.length) {
        onTranscript(words.join(" "));
        setNotice("Transcript added. Review and edit it before sending.");
      }
    };
    current.onerror = event => {
      if (recognizer.current !== current || event.error === "aborted") return;
      setNotice(event.error === "not-allowed" || event.error === "service-not-allowed"
        ? "Microphone access was denied by your browser."
        : "Dictation failed (" + event.error + "). You can type your message.");
    };
    current.onend = () => {
      if (deadline.current) clearTimeout(deadline.current);
      deadline.current = null;
      if (recognizer.current === current) recognizer.current = null;
      setListening(false);
    };
    recognizer.current = current;
    setNotice("Listening. Your browser may process audio using its speech provider.");
    try {
      current.start();
      setListening(true);
      deadline.current = setTimeout(() => {
        if (recognizer.current === current) {
          current.stop();
          setNotice("Dictation ended after 30 seconds. Review your transcript.");
        }
      }, 30000);
    } catch {
      recognizer.current = null;
      setListening(false);
      setNotice("Unable to start dictation. Check browser microphone permissions.");
    }
  }
  return (
    <span className="onesa-voice-control">
      <button type="button" disabled={disabled || (!supported && !listening)}
        aria-label={listening ? "Stop dictation" : "Dictate message"}
        aria-pressed={listening}
        onClick={listening ? stop : start}>
        {listening ? "Stop mic" : "🎙 Dictate"}
      </button>
      <span className="onesa-voice-notice" role="status" aria-live="polite">
        {notice || (!supported ? "Dictation not supported in this browser." : "Browser speech recognition may send audio to the browser provider.")}
      </span>
    </span>
  );
}

export function SpeechReader({text, language}: {text: string; language: string}) {
  const supported = useSyncExternalStore(subscribeBrowserCapability, canSpeak, unavailableOnServer);
  const [status, setStatus] = useState<"idle"|"playing"|"paused">("idle");
  const [rate, setRate] = useState(1);
  const [voiceId, setVoiceId] = useState("");
  const [voices, setVoices] = useState<SpeechSynthesisVoice[]>([]);
  const [error, setError] = useState("");
  const active = useRef<SpeechSynthesisUtterance | null>(null);

  useEffect(() => {
    if (!supported) return;
    const engine = window.speechSynthesis;
    const updateVoices = () => setVoices(engine.getVoices().filter(voice =>
      voice.lang.startsWith(language.slice(0, 2))));
    const frame = requestAnimationFrame(updateVoices);
    engine.addEventListener("voiceschanged", updateVoices);
    return () => {
      cancelAnimationFrame(frame);
      engine.removeEventListener("voiceschanged", updateVoices);
      if (active.current) {
        active.current = null;
        engine.cancel();
      }
    };
  }, [language, supported]);

  function play() {
    if (!supported || !text.trim()) return;
    const engine = window.speechSynthesis;
    engine.cancel();
    active.current = null;
    const utterance = new SpeechSynthesisUtterance(text.slice(0, 12000));
    utterance.lang = language;
    utterance.rate = rate;
    const voice = voices.find(v => v.voiceURI === voiceId);
    if (voice) utterance.voice = voice;
    utterance.onstart = () => { if (active.current === utterance) setStatus("playing"); };
    utterance.onpause = () => { if (active.current === utterance) setStatus("paused"); };
    utterance.onresume = () => { if (active.current === utterance) setStatus("playing"); };
    utterance.onend = () => {
      if (active.current === utterance) { active.current = null; setStatus("idle"); }
    };
    utterance.onerror = () => {
      if (active.current === utterance) {
        active.current = null; setStatus("idle");
        setError("Voice playback failed in this browser.");
      }
    };
    active.current = utterance;
    setError(text.length > 12000
      ? "Playback is limited to the first 12,000 characters." : "");
    setStatus("playing");
    try { engine.speak(utterance); }
    catch {
      active.current = null;
      setStatus("idle");
      setError("Voice playback is unavailable.");
    }
  }
  function stop() {
    if (!supported) return;
    active.current = null;
    window.speechSynthesis.cancel();
    setStatus("idle");
  }
  function pause() {
    window.speechSynthesis.pause();
    setStatus("paused");
  }
  function resume() {
    window.speechSynthesis.resume();
    setStatus("playing");
  }
  return (
    <div className="onesa-voice-control" aria-label="AI response speech">
      <button type="button" disabled={!supported} onClick={play}
        aria-label={status === "idle" ? "Listen to AI response" : "Replay AI response"}>
        {status === "idle" ? "▶ Listen" : "↻ Replay"}
      </button>
      {status === "playing" && <button type="button" onClick={pause} aria-label="Pause speech">Pause</button>}
      {status === "paused" && <button type="button" onClick={resume} aria-label="Resume speech">Resume</button>}
      {status !== "idle" && <button type="button" onClick={stop} aria-label="Stop speech">Stop</button>}
      <label>Speed
        <select aria-label="Voice speed" value={rate} onChange={e => setRate(Number(e.target.value))}>
          <option value="0.75">0.75×</option>
          <option value="1">1×</option>
          <option value="1.25">1.25×</option>
          <option value="1.5">1.5×</option>
        </select>
      </label>
      {voices.length > 0 && <label>Voice
        <select aria-label="Voice selection" value={voiceId} onChange={e => setVoiceId(e.target.value)}>
          <option value="">Browser default</option>
          {voices.map(voice => <option key={voice.voiceURI} value={voice.voiceURI}>{voice.name}</option>)}
        </select>
      </label>}
      <span className="onesa-voice-notice" role="status" aria-live="polite">
        {error || (!supported ? "Voice output unavailable." : "Synthetic browser voice · availability depends on device.")}
      </span>
    </div>
  );
}
