import { useState } from "react";
import { api, errText, type Me } from "../api";
import { Button, Card, Row } from "../components/ui";
import { days, fmtBytes, fmtDate } from "../format";
import { tg } from "../tg";
import type { Screen } from "../App";

export function Home({ me, setMe, go }: { me: Me; setMe: (m: Me) => void; go: (s: Screen) => void }) {
  const sub = me.subscription;
  const [busy, setBusy] = useState(false);

  async function trial() {
    setBusy(true);
    try {
      setMe(await api.trial());
      tg.HapticFeedback.notificationOccurred("success");
      go("connect");
    } catch (e) {
      tg.showAlert(errText(e));
    } finally {
      setBusy(false);
    }
  }

  const progress = sub.active ? Math.min(100, (sub.days_left / 30) * 100) : 0;

  return (
    <div className="screen">
      <Card className={`status ${sub.active ? "on" : "off"}`}>
        <div className="status-top">
          <span className={`dot ${sub.active ? "on" : ""}`} />
          <span className="status-label">{sub.active ? "Подписка активна" : sub.expires_at ? "Подписка закончилась" : "Нет подписки"}</span>
        </div>
        {sub.active ? (
          <>
            <div className="status-big">{days(sub.days_left)}</div>
            <div className="status-sub">до {fmtDate(sub.expires_at!)}</div>
            <div className="bar"><div style={{ width: `${progress}%` }} /></div>
            <div className="status-meta">
              <span>📶 {fmtBytes(sub.traffic_used)} · без лимита</span>
              <span>📱 до {sub.device_limit} устройств</span>
            </div>
          </>
        ) : (
          <div className="status-sub">
            {sub.trial_available ? "Попробуйте бесплатно — 3 дня без ограничений" : "Продлите подписку, ключ останется прежним"}
          </div>
        )}
      </Card>

      {sub.active ? (
        <>
          <Button onClick={() => go("connect")}>🚀 Подключиться</Button>
          <Button variant="secondary" onClick={() => go("plans")}>Продлить подписку</Button>
        </>
      ) : (
        <>
          {sub.trial_available && <Button loading={busy} onClick={trial}>🎁 Попробовать 3 дня бесплатно</Button>}
          <Button variant={sub.trial_available ? "secondary" : "primary"} onClick={() => go("plans")}>
            Выбрать тариф · от 99 ₽/мес
          </Button>
        </>
      )}

      {me.servers.length > 0 && (
        <>
          <h3 className="section">Локации</h3>
          <Card className="locations">
            {me.servers.map((s) => (
              <span key={s.name} className="chip">{s.flag} {s.name}</span>
            ))}
          </Card>
        </>
      )}

      <Card className="list">
        {sub.expires_at && <Row icon="🔑" title="Ключ и инструкция" subtitle="QR-код, ссылка, приложения" onClick={() => go("connect")} />}
        <Row icon="👥" title="Пригласить друга" subtitle="+7 дней за каждую оплату друга" onClick={() => go("referral")} />
        {me.support_username && (
          <Row icon="💬" title="Поддержка" subtitle="Ответим в Telegram" onClick={() => tg.openTelegramLink(`https://t.me/${me.support_username}`)} />
        )}
      </Card>
    </div>
  );
}
