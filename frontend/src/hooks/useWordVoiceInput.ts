import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError } from "../api/client";

export const MAX_VOICE_SECONDS = 60;
const MAX_AUDIO_BYTES = 8 * 1024 * 1024;

type VoicePhase = "idle" | "requesting" | "recording" | "transcribing";

type UseWordVoiceInputOptions = {
  profileId: number;
  onWords: (words: string[]) => void;
};

const preferredMimeTypes = [
  "audio/webm;codecs=opus",
  "audio/mp4",
  "audio/webm",
  "audio/ogg;codecs=opus",
];

function chooseMimeType(): string | undefined {
  if (typeof MediaRecorder === "undefined") return undefined;
  return preferredMimeTypes.find((mime) => MediaRecorder.isTypeSupported(mime));
}

function extensionFor(mime: string): string {
  if (mime.includes("mp4")) return "m4a";
  if (mime.includes("ogg")) return "ogg";
  if (mime.includes("wav")) return "wav";
  return "webm";
}

function microphoneErrorMessage(error: unknown): string {
  const name = (error as { name?: string } | null)?.name;
  if (name === "NotAllowedError" || name === "SecurityError") {
    return "没有获得话筒权限，请在浏览器设置中允许后重试";
  }
  if (name === "NotFoundError" || name === "DevicesNotFoundError") {
    return "没有找到可用话筒，请检查设备后重试";
  }
  return "话筒暂时无法使用，请重试或继续键盘输入";
}

export function useWordVoiceInput({
  profileId,
  onWords,
}: UseWordVoiceInputOptions) {
  const [phase, setPhase] = useState<VoicePhase>("idle");
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<number | null>(null);
  const timeoutRef = useRef<number | null>(null);
  const ignoreStopRef = useRef(false);
  const mountedRef = useRef(true);
  const onWordsRef = useRef(onWords);
  onWordsRef.current = onWords;

  const isSupported =
    typeof navigator !== "undefined" &&
    typeof navigator.mediaDevices?.getUserMedia === "function" &&
    typeof MediaRecorder !== "undefined";

  const clearTimers = useCallback(() => {
    if (timerRef.current !== null) window.clearInterval(timerRef.current);
    if (timeoutRef.current !== null) window.clearTimeout(timeoutRef.current);
    timerRef.current = null;
    timeoutRef.current = null;
  }, []);

  const releaseStream = useCallback(() => {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
  }, []);

  const transcribeRecording = useCallback(
    async (mimeType: string) => {
      clearTimers();
      releaseStream();
      recorderRef.current = null;
      const chunks = chunksRef.current;
      chunksRef.current = [];
      const blob = new Blob(chunks, { type: mimeType || "audio/webm" });
      if (!mountedRef.current) return;
      if (blob.size === 0) {
        setPhase("idle");
        setError("录音太短，没有采集到声音，请重试");
        return;
      }
      if (blob.size > MAX_AUDIO_BYTES) {
        setPhase("idle");
        setError("录音太大了，请控制在 60 秒以内");
        return;
      }

      setPhase("transcribing");
      setMessage("正在整理英文单词…");
      try {
        const file = new File(
          [blob],
          `wordnest-recording.${extensionFor(blob.type)}`,
          { type: blob.type },
        );
        const result = await api.transcribeVoice(profileId, file);
        if (!mountedRef.current) return;
        onWordsRef.current(result.words);
        setError(null);
        setMessage(`已识别 ${result.words.length} 个单词，请核对后统一补全`);
      } catch (err) {
        if (!mountedRef.current) return;
        setError(err instanceof ApiError ? err.message : "语音识别失败，请重试或手工输入");
        setMessage(null);
      } finally {
        if (mountedRef.current) setPhase("idle");
      }
    },
    [clearTimers, profileId, releaseStream],
  );

  const stopRecording = useCallback(() => {
    const recorder = recorderRef.current;
    if (!recorder || recorder.state === "inactive") return;
    clearTimers();
    recorder.stop();
  }, [clearTimers]);

  const startRecording = useCallback(async () => {
    if (!isSupported || phase !== "idle") return;
    setPhase("requesting");
    setError(null);
    setMessage("正在请求话筒权限…");
    ignoreStopRef.current = false;
    chunksRef.current = [];
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });
      if (!mountedRef.current) {
        stream.getTracks().forEach((track) => track.stop());
        return;
      }
      streamRef.current = stream;
      const mimeType = chooseMimeType();
      const recorder = mimeType
        ? new MediaRecorder(stream, { mimeType, audioBitsPerSecond: 64_000 })
        : new MediaRecorder(stream, { audioBitsPerSecond: 64_000 });
      recorderRef.current = recorder;
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) chunksRef.current.push(event.data);
      };
      recorder.onerror = () => {
        ignoreStopRef.current = true;
        clearTimers();
        releaseStream();
        if (mountedRef.current) {
          setPhase("idle");
          setMessage(null);
          setError("录音中断了，请重试");
        }
      };
      recorder.onstop = () => {
        if (ignoreStopRef.current) return;
        void transcribeRecording(recorder.mimeType || mimeType || "audio/webm");
      };
      recorder.start();
      const startedAt = Date.now();
      setElapsedSeconds(0);
      setPhase("recording");
      setMessage("请逐个说出英语单词，说完后点停止");
      timerRef.current = window.setInterval(() => {
        setElapsedSeconds(Math.min(MAX_VOICE_SECONDS, Math.floor((Date.now() - startedAt) / 1000)));
      }, 500);
      timeoutRef.current = window.setTimeout(stopRecording, MAX_VOICE_SECONDS * 1000);
    } catch (err) {
      clearTimers();
      releaseStream();
      if (mountedRef.current) {
        setPhase("idle");
        setMessage(null);
        setError(microphoneErrorMessage(err));
      }
    }
  }, [clearTimers, isSupported, phase, releaseStream, stopRecording, transcribeRecording]);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      ignoreStopRef.current = true;
      clearTimers();
      const recorder = recorderRef.current;
      if (recorder && recorder.state !== "inactive") recorder.stop();
      releaseStream();
    };
  }, [clearTimers, releaseStream]);

  return {
    phase,
    elapsedSeconds,
    message,
    error,
    isSupported,
    isRecording: phase === "recording",
    isBusy: phase === "requesting" || phase === "transcribing",
    startRecording,
    stopRecording,
  };
}
