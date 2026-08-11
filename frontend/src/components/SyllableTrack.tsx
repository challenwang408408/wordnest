import { useEffect, useState } from "react";
import { splitSyllables } from "../hooks/useSpeech";

type Props = {
  syllables: string;
  fallback: string;
  playing: boolean;
  onDone?: () => void;
  onActivate?: () => void;
  ariaLabel?: string;
};

export function SyllableTrack({
  syllables,
  fallback,
  playing,
  onDone,
  onActivate,
  ariaLabel,
}: Props) {
  const parts = splitSyllables(syllables, fallback);
  const [active, setActive] = useState(-1);
  const reduceMotion =
    typeof window !== "undefined" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  useEffect(() => {
    if (!playing) {
      setActive(-1);
      return;
    }
    if (reduceMotion) {
      setActive(parts.length - 1);
      const t = window.setTimeout(() => onDone?.(), 400);
      return () => window.clearTimeout(t);
    }
    let i = 0;
    setActive(0);
    const timer = window.setInterval(() => {
      i += 1;
      if (i >= parts.length) {
        window.clearInterval(timer);
        setActive(-1);
        onDone?.();
        return;
      }
      setActive(i);
    }, 220);
    return () => window.clearInterval(timer);
  }, [playing, parts.length, reduceMotion, onDone]);

  const trackClass = `syllable-track${parts.length === 1 ? " is-single" : ""}${
    onActivate ? " is-interactive" : ""
  }`;
  const chips = (
    <>
      {parts.map((part, index) => (
        <span
          key={`${part}-${index}`}
          className={`syllable-chip${active === index ? " active" : ""}`}
        >
          {part}
        </span>
      ))}
    </>
  );

  return onActivate ? (
    <button
      type="button"
      className={trackClass}
      aria-label={ariaLabel || `朗读 ${fallback} 音节`}
      onClick={onActivate}
    >
      {chips}
    </button>
  ) : (
    <div className={trackClass} aria-label="音节声轨">
      {chips}
    </div>
  );
}
