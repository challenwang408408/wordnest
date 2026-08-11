import { type FormEvent, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { api } from "../../api/client";
import { ArrowRight, KeyRound } from "lucide-react";
import { BrandLockup } from "../../components/BrandLockup";

export function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const sessionExpired = Boolean(
    (location.state as { sessionExpired?: boolean } | null)?.sessionExpired,
  );

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const result = await api.login(code);
      if (!result.authenticated) {
        setError(result.message || "访问码不对，请再试一次");
        return;
      }
      navigate("/select", { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "登录失败");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="auth-stage">
      <section className="auth-visual" aria-label="城市英雄学习主题插画">
        <BrandLockup inverse />
        <div className="auth-visual__copy">
          <p className="eyebrow">今晚的小任务</p>
          <h1>每认识一个词，<br />能力就长出一点。</h1>
          <p>给孩子一条自己能走完的学习路径，也给家长一个看得懂的成长记录。</p>
        </div>
      </section>
      <section className="surface login-panel stack">
        <div className="login-heading">
          <p className="eyebrow">家庭入口</p>
          <h2>回到词芽</h2>
          <p className="page-sub">输入 4 位家庭访问码，继续今天的学习任务。</p>
        </div>
        <form className="stack" onSubmit={onSubmit}>
          {sessionExpired ? (
            <div className="error-banner" role="status">
              登录已失效，请重新输入家庭访问码。
            </div>
          ) : null}
          <div className="field">
            <label htmlFor="access">
              <KeyRound size={16} aria-hidden="true" />
              家庭访问码
            </label>
            <input
              id="access"
              type="password"
              autoComplete="current-password"
              value={code}
              onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 4))}
              inputMode="numeric"
              pattern="[0-9]{4}"
              maxLength={4}
              placeholder="请输入 4 位访问码"
              aria-invalid={error ? "true" : "false"}
              aria-describedby={error ? "access-error" : undefined}
              required
            />
          </div>
          {error ? (
            <div id="access-error" className="error-banner" role="alert" aria-live="polite">
              {error}
            </div>
          ) : null}
          <button className="btn btn-primary" type="submit" disabled={loading}>
            {loading ? "正在进入…" : "进入词芽"}
            {!loading ? <ArrowRight size={18} aria-hidden="true" /> : null}
          </button>
        </form>
      </section>
    </main>
  );
}
