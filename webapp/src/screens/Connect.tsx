import { QRCodeSVG } from "qrcode.react";
import { useState } from "react";
import type { Me } from "../api";
import { Button, Card } from "../components/ui";
import { CLIENTS, PLATFORM_NAMES } from "../clients";
import { detectPlatform, haptic, tg, type Platform } from "../tg";

export function Connect({ me, go }: { me: Me; go: (s: "plans") => void }) {
  const [platform, setPlatform] = useState<Platform>(detectPlatform());
  const [showQr, setShowQr] = useState(false);
  const [copied, setCopied] = useState(false);
  const url = me.subscription.sub_url;
  const token = url.split("/").pop();
  const apps = CLIENTS[platform];
  const [appId, setAppId] = useState(apps[0].id);
  const app = apps.find((a) => a.id === appId) ?? apps[0];

  async function copy() {
    try { await navigator.clipboard.writeText(url); } catch { tg.showAlert(url); return; }
    setCopied(true);
    tg.HapticFeedback.notificationOccurred("success");
    setTimeout(() => setCopied(false), 1500);
  }

  if (!me.subscription.active) {
    return (
      <div className="screen center-col">
        <h2>Подписка не активна</h2>
        <p className="muted">Оформите или продлите подписку — ключ останется тем же.</p>
        <Button onClick={() => go("plans")}>Выбрать тариф</Button>
      </div>
    );
  }

  return (
    <div className="screen">
      <h2 className="title">Подключение</h2>
      <div className="tabs">
        {(Object.keys(CLIENTS) as Platform[]).map((p) => (
          <button key={p} className={`tab ${p === platform ? "sel" : ""}`}
                  onClick={() => { haptic(); setPlatform(p); setAppId(CLIENTS[p][0].id); }}>
            {PLATFORM_NAMES[p]}
          </button>
        ))}
      </div>

      <Card className="step">
        <div className="step-n">1</div>
        <div className="step-body">
          <div className="step-title">Установите приложение</div>
          <div className="seg">
            {apps.map((a) => (
              <button key={a.id} className={`seg-item ${a.id === app.id ? "sel" : ""}`} onClick={() => { haptic(); setAppId(a.id); }}>
                {a.name}
              </button>
            ))}
          </div>
          <Button variant="secondary" onClick={() => tg.openLink(app.store)}>Скачать {app.name}</Button>
        </div>
      </Card>

      <Card className="step">
        <div className="step-n">2</div>
        <div className="step-body">
          <div className="step-title">Добавьте подписку</div>
          <Button onClick={() => tg.openLink(`${location.origin}/connect/${token}/${app.id}`)}>
            ➕ Добавить в {app.name}
          </Button>
          <p className="muted small">Не открылось? Скопируйте ссылку и вставьте её в приложение через «+».</p>
          <div className="key">{url}</div>
          <div className="two">
            <Button variant="secondary" onClick={copy}>{copied ? "✓ Скопировано" : "📋 Копировать"}</Button>
            <Button variant="secondary" onClick={() => setShowQr(!showQr)}>{showQr ? "Скрыть QR" : "▦ QR-код"}</Button>
          </div>
          {showQr && <div className="qr"><QRCodeSVG value={url} size={220} includeMargin /></div>}
        </div>
      </Card>

      <Card className="step">
        <div className="step-n">3</div>
        <div className="step-body">
          <div className="step-title">Включите VPN</div>
          <p className="muted small">Выберите любую локацию и нажмите кнопку подключения в приложении. Готово 🎉</p>
          {me.bypass.available && (
            <p className="muted small">
              🛡 Если мобильный интернет работает только по белым спискам, выберите в приложении сервер
              «Обход белых списков». Лимит — {Math.round(me.bypass.limit / 1024 ** 3)} ГБ в сутки.
            </p>
          )}
        </div>
      </Card>
    </div>
  );
}
