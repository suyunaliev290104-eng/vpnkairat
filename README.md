# VPN-бот с мини-приложением для Telegram

Продажа VPN-подписок прямо в Telegram. Клиент открывает бота, жмёт «Открыть VPN»,
выбирает тариф, платит и сразу получает ключ, QR-код и пошаговую инструкцию.

- **Протокол:** VLESS + Reality (Xray) через панель **3x-ui**. Его сложно заблокировать.
- **Оплата:** Telegram Stars, CryptoBot (USDT), lava.top (карты РФ / СБП / зарубежные).
  ЮKassa и другие системы подключаются одним файлом (см. ниже).
- **Одна ссылка подписки на все серверы.** Новый сервер появится у клиентов без перевыдачи ключей.
- **Бот:** пробный период, напоминания за 3 дня и за 1 день, автоотключение, реферальная программа.
- **Админка в боте (`/admin`):** статистика и выручка, поиск пользователя, +7/+30 дней,
  отключение, рассылка, серверы.

## Тарифы по умолчанию

| Срок | Карта/СБП | ₽/мес | Выгода | Stars | USDT |
|---|---|---|---|---|---|
| 1 мес | 159 ₽ | 159 ₽ | — | 150⭐ | 2 |
| 3 мес | 399 ₽ | 133 ₽ | −16% | 380⭐ | 5 |
| 6 мес | 699 ₽ | 117 ₽ | −27% | 660⭐ | 9 |
| 12 мес | 1190 ₽ | 99 ₽ | −38% | 1080⭐ | 14 |

Цены задаются в `backend/app/plans.py`. Пробный период, бонус за друга и лимит
устройств задаются в `.env`.

---

## Что понадобится

1. **Сервер для бота.** Любой VPS с Docker (1 vCPU / 1 ГБ RAM хватает) и домен,
   A-запись которого указывает на этот сервер.
2. **Один или несколько VPN-серверов.** VPS за рубежом (Нидерланды, Германия, Финляндия…)
   с чистой Ubuntu 22.04+ или Debian 12. Бот и VPN можно поставить на один сервер,
   но тогда для панели и бота нужны разные порты; проще держать их раздельно.
3. **Бот в @BotFather.** Из него нужны `BOT_TOKEN` и username.

## Шаг 1. VPN-сервер

На каждом VPN-сервере выполните (от root):

```bash
curl -fsSL https://raw.githubusercontent.com/<ваш-репозиторий>/main/scripts/install_xui.sh -o install_xui.sh
```

```bash
bash install_xui.sh --name "Нидерланды" --flag 🇳🇱
```

Скрипт поставит 3x-ui, включит BBR, создаст inbound VLESS Reality на 443 порту
и напечатает готовую команду `/addserver {...}`. Её вы позже отправите боту.

> Бот обращается к панели по HTTP по случайному порту и пути. Закройте этот порт
> фаерволом для всех, кроме IP сервера с ботом: `ufw allow from <IP_бота> to any port <порт_панели>`.

## Шаг 2. Бот

```bash
git clone <ваш-репозиторий> vpn-bot && cd vpn-bot/deploy
```

```bash
cp .env.example .env && nano .env
```

Заполните как минимум `DOMAIN`, `PUBLIC_URL`, `WEBAPP_URL`, `POSTGRES_PASSWORD`,
`BOT_TOKEN`, `BOT_USERNAME` и `ADMIN_IDS` (ваш Telegram ID в формате `[123456789]`).

```bash
docker compose up -d --build
```

HTTPS-сертификат Caddy получит автоматически. Кнопка мини-приложения в меню бота
тоже настроится сама при старте. Проверка: `https://<домен>/health` → `{"ok":true}`.

Затем напишите боту `/admin`, отправьте команду `/addserver {...}` из шага 1, и всё готово.
Если сервер добавлен, когда клиенты уже есть, отправьте `/resync`: их ключи
появятся на новом сервере в течение 10 минут.

## Шаг 3. Оплата

Способ оплаты показывается клиенту только тогда, когда для него заполнены настройки.

### Telegram Stars
Работает сразу, настраивать ничего не нужно. Выводить звёзды можно через @BotFather → Fragment.

### CryptoBot
1. @CryptoBot → Crypto Pay → Create App, скопируйте токен в `CRYPTOBOT_TOKEN`.
2. Там же Webhooks → включить → URL `https://<домен>/webhooks/cryptobot`.
3. Для тестов: `CRYPTOBOT_TESTNET=true` и токен из @CryptoTestnetBot.

### lava.top
1. В кабинете lava.top создайте продукт с **4 офферами** с ценами 159 / 399 / 699 / 1190 ₽.
2. Впишите ID офферов: `LAVATOP_OFFERS={"m1":"…","m3":"…","m6":"…","m12":"…"}`.
3. API-ключ впишите в `LAVATOP_API_KEY`.
4. Вебхук: URL `https://<домен>/webhooks/lavatop`, авторизация «API key». Придумайте
   секрет и впишите его туда и в `LAVATOP_WEBHOOK_SECRET`.

> ⚠️ Модуль lava.top (`backend/app/payments/lavatop.py`) написан по их публичному API v2
> (`POST /api/v2/invoice`, поля `email`, `offerId`, `currency`; вебхук с `contractId` и `status`).
> Во время разработки документация `gate.lava.top` была недоступна. **Перед запуском сверьте
> поля с актуальной документацией** и сделайте одну тестовую оплату.

### Как добавить ЮKassa (или любую другую платёжку)
Создайте `backend/app/payments/yookassa.py`:

```python
from app.payments.base import InvoiceResult, PaymentProvider, WebhookResult
from app.payments.registry import register

@register
class YooKassaProvider(PaymentProvider):
    name = "yookassa"            # вебхук будет на /webhooks/yookassa
    title = "Карта (ЮKassa)"
    currency = "RUB"
    needs_email = True           # для чека 54-ФЗ

    def price(self, plan): return plan.rub
    def enabled(self, settings): return bool(settings.yookassa_shop_id)  # + поле в config.py

    async def create_invoice(self, payment, plan, user) -> InvoiceResult:
        # POST https://api.yookassa.ru/v3/payments → confirmation.confirmation_url
        ...
        return InvoiceResult(payment_url=url, provider_payment_id=yk_payment_id)

    async def parse_webhook(self, request) -> WebhookResult:
        # проверить подлинность (IP ЮKassa или GET /v3/payments/{id}), вернуть статус
        ...
        return WebhookResult(provider_payment_id=yk_payment_id, paid=status == "succeeded")
```

Затем добавьте `yookassa` в `load_builtin()` в `registry.py` и настройки в `config.py`/`.env`.
Остальной код (мини-приложение, начисление дней, рефералы, защита от двойных начислений)
трогать не нужно.

---

## Как это устроено

```
backend/app/
  plans.py              тарифы и цены
  config.py             настройки из .env
  models.py             пользователи, подписки, серверы, платежи
  services/             логика подписки (пробный период, продление, рефералы) и админки
  vpn/                  3x-ui API, генерация vless-ссылок, синхронизация клиентов
  payments/             ядро оплаты + stars / cryptobot / lavatop
  api/                  API мини-приложения, вебхуки, /sub/<token>, /connect/<token>/<app>
  bot/                  /start, /admin, оплата Stars, тексты уведомлений
  scheduler.py          раз в 10 минут: напоминания, отключение истёкших, досинхронизация
webapp/                 мини-приложение (React + Vite)
deploy/                 Dockerfile, docker-compose (app + Postgres + Caddy)
scripts/install_xui.sh  установка VPN-сервера
```

Что важно знать:
- **Повторное уведомление об оплате не начислит дни второй раз.** Платёж переводится
  из `pending` в `paid` одной атомарной операцией.
- **Если VPN-сервер недоступен в момент оплаты**, платёж всё равно засчитывается и срок
  продлевается, а сервер досинхронизируется в фоне.
- **Истёкшая подписка отключает клиента, но не удаляет его.** После продления работает
  тот же ключ.
- **Каждый запрос мини-приложения проверяется по подписи Telegram** (`initData`).
- **Ссылки на VPN-клиенты** (Happ, v2RayTun, Hiddify) лежат в `webapp/src/clients.ts`.
  Проверьте их перед запуском.

## Разработка

```bash
cd backend && python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'
```

```bash
cd backend && .venv/bin/pytest
```

```bash
cd webapp && npm install && npm run build
```

Локальный запуск (бот в режиме polling, база SQLite): положите `.env` в `backend/` и выполните

```bash
cd backend && .venv/bin/uvicorn app.main:app --reload
```

Чтобы открыть мини-приложение в браузере без Telegram, передайте подписанный
`initData` параметром: `http://localhost:8000/?initData=<...>`.
