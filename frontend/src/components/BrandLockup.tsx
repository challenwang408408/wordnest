import { Sprout } from "lucide-react";

type Props = {
  compact?: boolean;
  inverse?: boolean;
};

export function BrandLockup({ compact = false, inverse = false }: Props) {
  return (
    <div
      className={`brand-lockup${compact ? " is-compact" : ""}${inverse ? " is-inverse" : ""}`}
      aria-label="词芽 WordNest"
    >
      <span className="brand-mark" aria-hidden="true">
        <Sprout strokeWidth={2.4} />
      </span>
      <span className="brand-copy">
        <strong>词芽</strong>
        <small>WORDNEST</small>
      </span>
    </div>
  );
}
