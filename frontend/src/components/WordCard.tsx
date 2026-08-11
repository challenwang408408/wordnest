import { useState } from "react";
import { SyllableTrack } from "./SyllableTrack";
import { useSpeech } from "../hooks/useSpeech";

type Props = {
  spelling: string;
  ipa?: string;
  syllables?: string;
  meaningZh?: string;
  showMeaning?: boolean;
  exampleEn?: string;
  exampleZh?: string;
};

export function WordCard({
  spelling,
  ipa,
  syllables,
  meaningZh,
  showMeaning = true,
  exampleEn,
  exampleZh,
}: Props) {
  const { speak, voiceHint } = useSpeech();
  const [playing, setPlaying] = useState(false);

  function playWord() {
    const ok = speak(spelling);
    if (ok) setPlaying(true);
  }

  return (
    <article className="surface word-card">
      <div className="row word-card__heading">
        <div>
          <h2 className="word-spelling">{spelling}</h2>
          {ipa ? <p className="ipa">{ipa}</p> : null}
        </div>
        <button
          type="button"
          className="btn btn-secondary"
          aria-label="朗读单词"
          onClick={playWord}
        >
          听发音
        </button>
      </div>
      <SyllableTrack
        syllables={syllables || spelling}
        fallback={spelling}
        playing={playing}
        onDone={() => setPlaying(false)}
        onActivate={playWord}
        ariaLabel={`朗读 ${spelling} 音节`}
      />
      {showMeaning && meaningZh ? (
        <p style={{ margin: "14px 0 0", fontSize: "1.05rem" }}>{meaningZh}</p>
      ) : null}
      {exampleEn || exampleZh ? (
        <div className="word-example">
          {exampleEn ? <p className="word-example__en">{exampleEn}</p> : null}
          {exampleZh ? <p className="word-example__zh">{exampleZh}</p> : null}
        </div>
      ) : null}
      {voiceHint ? (
        <p className="error-banner" style={{ marginTop: 12 }}>
          {voiceHint}
        </p>
      ) : null}
    </article>
  );
}
