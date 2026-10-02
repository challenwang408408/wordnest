import type { Ref } from "react";
import { CircleX } from "lucide-react";
import type { QuizWord } from "../../types";

type Props = {
  ref?: Ref<HTMLDivElement>;
  word: QuizWord;
  picked: string;
  secondsLeft: number;
  totalSeconds: number;
};

const RING_RADIUS = 20;
const RING_LENGTH = 2 * Math.PI * RING_RADIUS;

/** 答错后的细看卡：倒计时期间把注意力留在这个词上。 */
export function WordStudyCard({ ref, word, picked, secondsLeft, totalSeconds }: Props) {
  const locked = secondsLeft > 0;
  const remaining = locked ? secondsLeft / totalSeconds : 0;

  return (
    <div
      ref={ref}
      className="word-study"
      role="status"
      aria-live="polite"
      tabIndex={-1}
    >
      <div className="word-study__head">
        <CircleX size={22} aria-hidden="true" />
        <div>
          <strong>选错了，先把它看清楚</strong>
          <p>你选的「{picked}」不是它的意思。</p>
        </div>
        <span className={locked ? "study-ring" : "study-ring is-done"} aria-hidden="true">
          <svg viewBox="0 0 48 48">
            <circle className="study-ring__track" cx="24" cy="24" r={RING_RADIUS} />
            <circle
              className="study-ring__fill"
              cx="24"
              cy="24"
              r={RING_RADIUS}
              strokeDasharray={RING_LENGTH}
              strokeDashoffset={RING_LENGTH * (1 - remaining)}
            />
          </svg>
          <b>{locked ? secondsLeft : "✓"}</b>
        </span>
      </div>

      <dl className="word-study__body">
        <div className="word-study__meaning">
          <dt>正确意思</dt>
          <dd>
            <span>{word.meaning_zh}</span>
            {word.part_of_speech ? <small>{word.part_of_speech}</small> : null}
          </dd>
        </div>
        <div className="word-study__example">
          <dt>放进句子里读一读</dt>
          {word.example_en || word.example_zh ? (
            <dd>
              {word.example_en ? (
                <p className="word-study__en">{highlight(word.example_en, word.spelling)}</p>
              ) : null}
              {word.example_zh ? <p className="word-study__zh">{word.example_zh}</p> : null}
            </dd>
          ) : (
            <dd className="word-study__empty">这个词还没有例句，点上面的音节再读两遍。</dd>
          )}
        </div>
      </dl>
    </div>
  );
}

function highlight(sentence: string, spelling: string) {
  const target = spelling.trim();
  if (!target) return sentence;
  const escaped = target.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const parts = sentence.split(new RegExp(`(${escaped})`, "i"));
  if (parts.length === 1) return sentence;
  return parts.map((part, index) =>
    part.toLowerCase() === target.toLowerCase()
      ? <mark key={index}>{part}</mark>
      : part,
  );
}
