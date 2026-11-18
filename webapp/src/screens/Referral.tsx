import { useEffect, useState } from "react";
import { api, errText, type RefResp } from "../api";
import { Button, Card, Loader } from "../components/ui";
import { days } from "../format";
import { tg } from "../tg";

export function Referral() {
  const [d, setD] = useState<RefResp | null>(null);
  useEffect(() => { api.referrals().then(setD).catch((e) => tg.showAlert(errText(e))); }, []);
  if (!d) return <Loader />;

  const share = () => {
    const text = "Пользуюсь этим VPN — быстрый и работает везде. Попробуй 3 дня бесплатно 👇";
    tg.openTelegramLink(`https://t.me/share/url?url=${encodeURIComponent(d.link)}&text=${encodeURIComponent(text)}`);
  };

  return (
    <div className="screen">
      <div className="hero">🎁</div>
      <h2 className="title center-text">Приглашайте друзей</h2>
      <p className="muted center-text">За каждую оплату друга вы получаете <b>+{days(d.bonus_days)}</b> подписки.</p>
      <Card className="stats">
        <div><span className="big">{d.invited}</span><span className="muted small">приглашено</span></div>
      </Card>
      <div className="key">{d.link}</div>
      <Button onClick={share}>📤 Поделиться ссылкой</Button>
      <Button variant="secondary" onClick={() => navigator.clipboard.writeText(d.link).then(() => tg.HapticFeedback.notificationOccurred("success"))}>
        📋 Скопировать
      </Button>
    </div>
  );
}
