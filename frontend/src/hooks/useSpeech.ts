import { useCallback, useEffect, useRef, useState } from "react";

type VoiceLike = { lang: string };

export function pickEnUsVoice<T extends VoiceLike>(voices: T[]): T | null {
  return (
    voices.find((v) => v.lang.toLowerCase() === "en-us") ??
    voices.find((v) => v.lang.toLowerCase().startsWith("en")) ??
    null
  );
}

/** 无可用发音时的可见提示；有 voice 时返回 null。 */
export function voiceAvailabilityMessage(
  hasSpeechApi: boolean,
  voices: VoiceLike[],
): string | null {
  if (!hasSpeechApi) {
    return "这台设备暂时不能朗读，请换一台手机试试";
  }
  return pickEnUsVoice(voices)
    ? null
    : "还没有可用的美式英语发音，请稍后再试或检查系统语音设置";
}

export function useSpeech() {
  const [voiceReady, setVoiceReady] = useState(false);
  const [voiceHint, setVoiceHint] = useState<string | null>(null);
  const voiceRef = useRef<SpeechSynthesisVoice | null>(null);

  useEffect(() => {
    const hasApi = "speechSynthesis" in window;
    if (!hasApi) {
      setVoiceHint(voiceAvailabilityMessage(false, []));
      return;
    }
    const refresh = () => {
      const voices = window.speechSynthesis.getVoices?.() ?? [];
      const voice = pickEnUsVoice(voices);
      voiceRef.current = voice;
      setVoiceReady(Boolean(voice));
      setVoiceHint(voiceAvailabilityMessage(true, voices));
    };
    refresh();
    window.speechSynthesis.addEventListener("voiceschanged", refresh);
    return () => {
      window.speechSynthesis.removeEventListener("voiceschanged", refresh);
    };
  }, []);

  const speak = useCallback((text: string, onBoundary?: (index: number) => void) => {
    if (!("speechSynthesis" in window)) {
      setVoiceHint(voiceAvailabilityMessage(false, []));
      return false;
    }
    const voice = voiceRef.current ?? pickEnUsVoice(window.speechSynthesis.getVoices?.() ?? []);
    if (!voice) {
      setVoiceHint(voiceAvailabilityMessage(true, []));
      return false;
    }
    window.speechSynthesis.cancel();
    const utter = new SpeechSynthesisUtterance(text);
    utter.voice = voice;
    utter.lang = voice.lang || "en-US";
    utter.rate = 0.92;
    utter.onboundary = () => {
      onBoundary?.(0);
    };
    window.speechSynthesis.speak(utter);
    setVoiceHint(null);
    return true;
  }, []);

  return { speak, voiceReady, voiceHint };
}

export function splitSyllables(syllables: string, fallback: string): string[] {
  const raw = (syllables || fallback).trim();
  if (!raw) return [fallback];
  const parts = raw.split(/[·•.-]+/).map((s) => s.trim()).filter(Boolean);
  return parts.length > 0 ? parts : [raw];
}
