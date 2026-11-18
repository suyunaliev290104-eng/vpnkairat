import { useEffect, useRef, useState } from "react";
import { api, ApiError, errText, type Me, type PlansResp } from "../api";
import { Button, Card, Loader } from "../components/ui";
import { fmtPrice, months } from "../format";
import { haptic, tg } from "../tg";

const PROVIDER_ICONS: Record<string, string> = { stars: "⭐", lavatop: "💳", cryptobot: "🪙" };

export function Plans({ me, setMe, onPaid }: { me: Me; setMe: (m: Me) => void; onPaid: () => void }) {
  const [data, setData] = useState<PlansResp | null>(null);
  const [planId, setPlanId] = useState("m12");
  const [provider, setProvider] = useState<string>("");
  const [email, setEmail] = useState(me.user.email ?? "");
  const [busy, setBusy] = useState(false);
  const [waiting, setWaiting] = useState(false);
  const [starsCancelled, setStarsCancelled] = useState(false);
  const startExpiry = useRef(me.subscription.expires_at);

  useEffect(() => {
    api.plans().then((d) => {
      setData(d);
      setProvider(d.providers.find((p) => p.name === "lavatop")?.name ?? d.providers[0]?.name ?? "");
    }).catch((e) => tg.showAlert(errText(e)));
  }, []);

  useEffect(() => {
    if (!waiting) return;
    const started = Date.now();
    const t = setInterval(async () => {
      try {
        const m = await api.me();
        if (m.subscription.expires_at !== startExpiry.current) {
          clearInterval(t);
          setMe(m);
          tg.HapticFeedback.notificationOccurred("success");
          onPaid();
        }
      } catch { /* retry */ }
      if (Date.now() - started > 120_000) { clearInterval(t); setWaiting(false); }
    }, 3000);
    return () => clearInterval(t);
  }, [waiting]);

  if (!data) return <Loader />;
  if (!data.providers.length) return <div className="screen"><Card>Оплата временно недоступна</Card></div>;

  const prov = data.providers.find((p) => p.name === provider)!;
  const plan = data.plans.find((p) => p.id === planId)!;
  const price = plan.prices[provider];
  const needEmail = prov.needs_email && !me.user.email;

  async function pay() {
    setBusy(true);
    try {
      if (needEmail) {
        if (!/^\S+@\S+\.\S+$/.test(email)) { tg.showAlert("Проверьте e-mail"); return; }
        setMe(await api.setEmail(email));
      }
      const r = await api.pay(planId, provider);
      if (r.kind === "invoice") {
        tg.openInvoice(r.payment_url, (status) => {
          if (status === "paid") setWaiting(true);
          else if (status === "cancelled" || status === "failed") setStarsCancelled(true);
        });
      } else {
        tg.openLink(r.payment_url);
        setWaiting(true);
      }
    } catch (e) {
      if (e instanceof ApiError && e.code === "email_required") setMe({ ...me, user: { ...me.user, email: null } });
      tg.showAlert(errText(e));
    } finally {
      setBusy(false);
    }
  }

  if (waiting) {
    return (
      <div className="screen center-col">
        <span className="spinner big" />
        <h2>Ждём подтверждения оплаты…</h2>
        <p className="muted">Обычно это занимает несколько секунд. Подписка продлится автоматически.</p>
        <Button variant="secondary" onClick={() => setWaiting(false)}>Назад к тарифам</Button>
      </div>
    );
  }

  return (
    <div className="screen">
      <h2 className="title">Выберите тариф</h2>
      <div className="plans">
        {data.plans.map((p) => (
          <button key={p.id} className={`plan ${p.id === planId ? "sel" : ""}`} onClick={() => { haptic(); setPlanId(p.id); }}>
            {p.badge && <span className={`badge ${p.id === "m12" ? "best" : ""}`}>{p.badge}</span>}
            <span className="plan-name">{months(p.months)}</span>
            <span className="plan-price">{fmtPrice(p.prices[provider].amount, p.prices[provider].currency)}</span>
            <span className="plan-per">
              {p.per_month_rub} ₽/мес{p.discount > 0 && <b className="disc"> −{p.discount}%</b>}
            </span>
          </button>
        ))}
      </div>

      <h3 className="section">Способ оплаты</h3>
      <Card className="list">
        {data.providers.map((p) => (
          <button key={p.name} className={`row radio ${p.name === provider ? "sel" : ""}`} onClick={() => { haptic(); setProvider(p.name); }}>
            <span className="row-icon">{PROVIDER_ICONS[p.name] ?? "💰"}</span>
            <span className="row-text"><span className="row-title">{p.title}</span></span>
            <span className="radio-dot" />
          </button>
        ))}
      </Card>

      {provider === "stars" && data.stars_shop_url && (
        <Card className={`stars-shop ${starsCancelled ? "attn" : ""}`}>
          <div className="stars-shop-text">
            <span className="row-title">{starsCancelled ? "Не хватило звёзд?" : "Нет звёзд?"}</span>
            <span className="row-sub">Купите их выгоднее, чем в самом Telegram, — по карте или СБП</span>
          </div>
          <Button variant="secondary" onClick={() => tg.openTelegramLink(data.stars_shop_url)}>⭐ Купить звёзды</Button>
        </Card>
      )}

      {needEmail && (
        <Card>
          <label className="label">E-mail для чека</label>
          <input className="input" type="email" inputMode="email" placeholder="you@mail.ru" value={email}
                 onChange={(e) => setEmail(e.target.value)} />
        </Card>
      )}

      <Button loading={busy} onClick={pay}>Оплатить {fmtPrice(price.amount, price.currency)}</Button>
      <p className="muted small center-text">Без автопродления. Ключ и настройки сохраняются при продлении.</p>
    </div>
  );
}
