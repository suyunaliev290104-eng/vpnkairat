# VPN в Telegram с мини-приложением — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Коммерческий VPN (VLESS+Reality на 3x-ui), продаваемый через Telegram-бота с мини-приложением; оплата Stars, CryptoBot, lava.top; ЮKassa подключается одним модулем.

**Architecture:** Один Python-процесс: FastAPI (API мини-приложения, вебхуки, ссылка подписки, раздача собранного React) + aiogram 3 (бот, polling или webhook) + APScheduler. Платёжки и VPN-панели — за интерфейсами `PaymentProvider` / `VpnProvider` с реестрами. PostgreSQL через SQLAlchemy 2 async.

**Tech Stack:** Python 3.12, FastAPI, aiogram 3, SQLAlchemy 2 + asyncpg/aiosqlite, pydantic-settings, httpx, APScheduler, pytest + pytest-asyncio + respx; React 18 + Vite + TypeScript + @telegram-apps/sdk-react; Docker Compose + Caddy.

**Spec:** `docs/superpowers/specs/2026-11-18-vpn-telegram-design.md`

## Global Constraints

- Тарифы (id → дни, RUB, XTR, USDT): `m1`→30, 159, 150, 2; `m3`→90, 399, 380, 5; `m6`→180, 699, 660, 9; `m12`→365, 1190, 1080, 14. Бейджи: `m3` «Популярный», `m12` «Выгоднее всего»; выгода считается от цены `m1`×месяцы.
- Пробный период 3 дня, один раз на аккаунт. Трафик без лимита. `limitIp=3` (до 3 устройств).
- Реферал: +7 дней пригласившему за каждую оплаченную покупку приглашённого. Себя пригласить нельзя; реферер фиксируется только при первом /start.
- Продление: от `max(now, expires_at)`.
- Все тексты интерфейса — на русском.
- Новая платёжка = новый файл в `app/payments/` + регистрация в `registry.py` + переменные в `.env`; остальной код не меняется.
- Все секреты только в `.env`; `.env.example` без значений.

## Review Focus

- Повторный вебхук того же платежа → дни начисляются один раз (тест в Task 5).
- Подписка истекла неделю назад, клиент платит → срок от сегодня, а не от старой даты (тест в Task 2).
- initData с неверной подписью или старше 24 ч → 401 (тест в Task 3).
- Сервер 3x-ui недоступен в момент оплаты → платёж засчитан, срок продлён, `needs_sync=True`, фоновая задача досинхронизирует (тест в Task 5 и Task 10).
- Подписка истекла → клиент отключён на всех серверах, не удалён (повторная оплата включает тот же UUID) (тест в Task 10).

---

## File Structure

```
backend/
  pyproject.toml
  app/
    config.py            Settings (pydantic-settings)
    plans.py             Plan dataclass, PLANS, per-month/выгода
    db.py                engine, session factory, init_db
    models.py            User, Subscription, Server, Payment
    services/subscription.py   trial, extend, referral bonus
    vpn/base.py          VpnProvider protocol, ClientSpec
    vpn/xui.py           XuiProvider (3x-ui HTTP API)
    vpn/sync.py          sync_user_to_servers, disable_user
    vpn/links.py         vless-ссылки + base64 подписка
    payments/base.py     PaymentProvider, InvoiceResult, WebhookResult
    payments/registry.py провайдеры по имени, включение по .env
    payments/service.py  create_payment, mark_paid (идемпотентно)
    payments/stars.py    Telegram Stars
    payments/cryptobot.py Crypto Pay API
    payments/lavatop.py  lava.top
    api/auth.py          проверка initData → current_user
    api/routes.py        /api/me, /api/plans, /api/pay, /api/email, /api/referrals, /api/trial
    api/webhooks.py      /webhooks/{provider}
    api/sub.py           /sub/{token}
    bot/setup.py         Bot, Dispatcher, роутеры
    bot/start.py         /start, deep-link ref
    bot/admin.py         /admin: статистика, поиск, продлить, рассылка, серверы
    bot/notify.py        тексты уведомлений
    scheduler.py         напоминания, отключение, досинхронизация
    main.py              FastAPI app + lifespan (бот, планировщик, статика)
  tests/ ...
webapp/                  React мини-приложение
deploy/ Dockerfile, docker-compose.yml, Caddyfile, .env.example
scripts/install_xui.sh   установка 3x-ui + inbound VLESS Reality
README.md
```

---

### Task 1: Каркас, конфиг, тарифы, модели

**Files:** Create `backend/pyproject.toml`, `app/config.py`, `app/plans.py`, `app/db.py`, `app/models.py`, `tests/conftest.py`, `tests/test_plans.py`

**Interfaces — Produces:**
- `Settings` поля: `bot_token, admin_ids: list[int], database_url, public_url, webapp_url, trial_days=3, referral_bonus_days=7, device_limit=3, cryptobot_token="", cryptobot_testnet=False, lavatop_api_key="", lavatop_webhook_secret="", lavatop_offers: dict[str,str]={}, support_username=""` ; `get_settings() -> Settings`
- `Plan(id, days, months, rub, xtr, usdt, badge: str|None)`; `PLANS: dict[str, Plan]`; `per_month_rub(plan) -> int`; `discount_percent(plan) -> int`
- Models: `User(id, tg_id unique, username, email, referrer_id FK null, is_admin, created_at)`; `Subscription(id, user_id unique, uuid, sub_token unique, expires_at null, trial_used, needs_sync, notified_3d, notified_1d, notified_expired)`; `Server(id, name, country, flag, panel_url, username, password, inbound_id, host, port, reality_pbk, reality_sni, reality_sid, enabled)`; `Payment(id, user_id, provider, provider_payment_id unique null, plan_id, amount, currency, status: pending|paid|failed, created_at, paid_at)`
- `tests/conftest.py`: фикстура `session` (in-memory aiosqlite), `user_factory`

- [ ] **Step 1: Тест** `test_plans.py`:
```python
def test_prices():
    assert [(p.rub, p.xtr, p.usdt) for p in PLANS.values()] == [(159,150,2),(399,380,5),(699,660,9),(1190,1080,14)]
def test_discounts():
    assert [discount_percent(PLANS[k]) for k in ("m1","m3","m6","m12")] == [0,16,27,38]
    assert per_month_rub(PLANS["m12"]) == 99
```
- [ ] **Step 2:** `pytest tests/test_plans.py` → FAIL (import)
- [ ] **Step 3:** Реализовать файлы. `discount_percent = round(100 - rub*100/(159*months))`, `per_month_rub = round(rub/months)`.
- [ ] **Step 4:** `pytest` → PASS
- [ ] **Step 5:** `git commit -m "feat: project skeleton, config, plans, models"`

### Task 2: Сервис подписки

**Files:** Create `app/services/subscription.py`, `tests/test_subscription.py`

**Interfaces — Produces:**
- `async get_or_create_user(s, tg_id, username, ref_tg_id: int|None) -> User`
- `async get_or_create_subscription(s, user) -> Subscription` (uuid4, `sub_token=secrets.token_urlsafe(16)`)
- `async start_trial(s, user) -> Subscription` — `ValueError("trial_used")` при повторе
- `async extend(s, user, days) -> Subscription` — от `max(now, expires_at)`, сбрасывает notified_*, ставит `needs_sync=True`
- `async apply_referral_bonus(s, payer: User) -> User|None`

- [ ] **Step 1: Тесты**: `test_trial_once` (второй вызов → ValueError), `test_extend_active_adds_to_expiry` (expires_at=now+10d, extend 30 → ≈now+40d), `test_extend_expired_starts_from_now` (expires_at=now-7d → ≈now+30d), `test_referrer_set_only_on_create`, `test_self_referral_ignored`, `test_referral_bonus_7_days`.
- [ ] **Step 2:** FAIL
- [ ] **Step 3:** Реализовать.
- [ ] **Step 4:** PASS
- [ ] **Step 5:** Commit `feat: subscription service`

### Task 3: Авторизация мини-приложения

**Files:** Create `app/api/auth.py`, `tests/test_auth.py`

**Interfaces — Produces:** `validate_init_data(init_data: str, bot_token: str, max_age=86400) -> dict` (бросает `InvalidInitData`); FastAPI dependency `current_user(...) -> User` по заголовку `Authorization: tma <initData>`.

Алгоритм Telegram: `secret = HMAC_SHA256(key="WebAppData", msg=bot_token)`; `data_check_string` = отсортированные `k=v` без `hash` через `\n`; сравнить `hmac.compare_digest`.

- [ ] **Step 1: Тесты** (хелпер `sign(params, token)` в тесте): валидная → dict с `user.id`; изменённое поле → InvalidInitData; `auth_date` = now-90000 → InvalidInitData.
- [ ] **Step 2–4:** FAIL → реализовать → PASS
- [ ] **Step 5:** Commit `feat: telegram initData auth`

### Task 4: VPN-провайдер 3x-ui, ссылки, синхронизация

**Files:** Create `app/vpn/base.py`, `app/vpn/xui.py`, `app/vpn/links.py`, `app/vpn/sync.py`, `tests/test_xui.py`, `tests/test_links.py`, `tests/test_sync.py`

**Interfaces — Produces:**
- `ClientSpec(uuid, email: str, expiry_ms: int, enabled: bool, limit_ip: int, sub_id: str)`
- `VpnProvider` Protocol: `async upsert_client(server: Server, spec: ClientSpec) -> None`; `async get_traffic(server, email) -> tuple[int,int]`
- `XuiProvider` (httpx): логин `POST {panel}/login` (cookie), `POST /panel/api/inbounds/addClient`, при «Duplicate» → `POST /panel/api/inbounds/updateClient/{uuid}`, `GET /panel/api/inbounds/getClientTraffics/{email}`. Тело клиента: `{"id":uuid,"email":email,"flow":"xtls-rprx-vision","limitIp":3,"expiryTime":ms,"enable":bool,"subId":sub_id,"totalGB":0}` внутри `settings` JSON-строкой с `id=inbound_id`.
- `build_vless(server, uuid, label) -> str` = `vless://{uuid}@{host}:{port}?type=tcp&security=reality&pbk={pbk}&fp=chrome&sni={sni}&sid={sid}&flow=xtls-rprx-vision#{flag} {name}`
- `build_subscription(servers, uuid) -> str` (base64 строк через `\n`)
- `async sync_user(s, user, provider) -> bool` — upsert на все `enabled` серверы, `email=f"tg{tg_id}"`; при любой ошибке `needs_sync=True`, вернуть False; иначе `needs_sync=False`.

- [ ] **Step 1: Тесты:** respx — `test_add_client_payload` (проверить flow, limitIp=3, expiryTime), `test_duplicate_falls_back_to_update`; `test_build_vless_contains_reality_params`; `test_sync_marks_needs_sync_on_error` (один сервер отдаёт 500).
- [ ] **Step 2–4:** FAIL → реализовать → PASS
- [ ] **Step 5:** Commit `feat: 3x-ui provider and subscription links`

### Task 5: Ядро платежей

**Files:** Create `app/payments/base.py`, `app/payments/registry.py`, `app/payments/service.py`, `tests/test_payment_service.py`

**Interfaces — Produces:**
- `InvoiceResult(payment_url: str|None, provider_payment_id: str|None, extra: dict)`; `WebhookResult(provider_payment_id: str, paid: bool)`
- `PaymentProvider` ABC: `name: str`, `title: str`, `currency: str`, `price(plan) -> Decimal|int`, `enabled(settings) -> bool`, `async create_invoice(payment: Payment, plan: Plan, user: User) -> InvoiceResult`, `async parse_webhook(request: Request) -> WebhookResult` (бросает `WebhookRejected`)
- `registry.get(name) -> PaymentProvider`, `registry.available() -> list[PaymentProvider]`, `register(provider_cls)`
- `async create_payment(s, user, plan_id, provider_name) -> tuple[Payment, InvoiceResult]`
- `async mark_paid(s, provider_name, provider_payment_id) -> Payment|None` — атомарно `pending→paid` (`UPDATE ... WHERE status='pending'`); если уже `paid` — вернуть None. При успехе: `extend`, `apply_referral_bonus`, `sync_user`, уведомление в бот через инжектируемый `notifier: Callable`.

- [ ] **Step 1: Тесты:** `test_mark_paid_extends_once` (два вызова → дни +30 один раз, второй вернул None); `test_mark_paid_unknown_id_returns_none`; `test_mark_paid_when_vpn_down_still_paid` (sync падает → payment.paid, expires продлён, needs_sync=True); `test_referral_bonus_on_paid`.
- [ ] **Step 2–4:** FAIL → реализовать → PASS
- [ ] **Step 5:** Commit `feat: payment core with idempotent mark_paid`

### Task 6: Telegram Stars

**Files:** Create `app/payments/stars.py`, `app/bot/payments.py`, `tests/test_stars.py`

**Interfaces:** `StarsProvider.create_invoice` → `bot.create_invoice_link(title, description, payload=f"pay:{payment.id}", currency="XTR", prices=[LabeledPrice(amount=plan.xtr)])`, `provider_payment_id=None` до оплаты. Бот: `pre_checkout_query` → ok, если payment pending; `successful_payment` → сохранить `telegram_payment_charge_id` как `provider_payment_id`, затем `mark_paid`. Мини-приложение открывает ссылку через `openInvoice`.

- [ ] Тесты: payload формат; `successful_payment` хэндлер вызывает `mark_paid` с charge_id (мок бота). FAIL → реализовать → PASS → Commit `feat: telegram stars payments`

### Task 7: CryptoBot

**Files:** Create `app/payments/cryptobot.py`, `tests/test_cryptobot.py`

**Interfaces:** `POST https://pay.crypt.bot/api/createInvoice` (testnet: `testnet-pay.crypt.bot`), заголовок `Crypto-Pay-API-Token`, тело `{asset:"USDT", amount:str(plan.usdt), payload:str(payment.id), expires_in:3600}` → `pay_url`/`mini_app_invoice_url`, `invoice_id`. Вебхук: проверка `crypto-pay-api-signature` = `HMAC_SHA256(key=sha256(token), msg=raw_body).hex()`; `update_type=="invoice_paid"` → `WebhookResult(str(invoice_id), True)`.

- [ ] Тесты (respx): создание счёта шлёт верные asset/amount; вебхук с верной подписью → paid; с неверной → WebhookRejected. FAIL → реализовать → PASS → Commit `feat: cryptobot payments`

### Task 8: lava.top

**Files:** Create `app/payments/lavatop.py`, `tests/test_lavatop.py`

**Interfaces:** Перед реализацией сверить поля с актуальной докой `gate.lava.top` (если хост недоступен — реализовать по описанию ниже и пометить в README). `POST https://gate.lava.top/api/v2/invoice`, заголовок `X-Api-Key`, тело `{email, offerId: settings.lavatop_offers[plan.id], currency:"RUB"}` → `paymentUrl`, `id`. Без `user.email` → `ValueError("email_required")` (API отвечает 400 с этим кодом). Вебхук: заголовок `X-Api-Key == settings.lavatop_webhook_secret` (иначе WebhookRejected); поля `contractId`, `status`; при `status in ("completed","subscription-active")` перепроверить `GET /api/v1/invoices/{id}` и вернуть paid.

- [ ] Тесты (respx): тело запроса с offerId из конфига; без email → ValueError; вебхук с неверным ключом → rejected; с верным + completed → paid. FAIL → реализовать → PASS → Commit `feat: lava.top payments`

### Task 9: HTTP API

**Files:** Create `app/api/routes.py`, `app/api/webhooks.py`, `app/api/sub.py`, `app/main.py`, `tests/test_api.py`

**Interfaces — Produces (JSON):**
- `GET /api/me` → `{user:{tg_id,username,email}, subscription:{active, expires_at, days_left, trial_available, sub_url, traffic_used}, servers:[{name,flag,country}]}`; `sub_url = f"{public_url}/sub/{sub_token}"`
- `GET /api/plans` → `{plans:[{id,days,months,badge,discount,per_month_rub, prices:{provider:{amount,currency}}}], providers:[{name,title,currency}]}`
- `POST /api/trial` → `/api/me`-ответ; 409 `trial_used`
- `POST /api/pay {plan_id, provider}` → `{payment_id, payment_url, kind:"invoice"|"link"}`; 400 `email_required`
- `POST /api/email {email}` (валидация EmailStr)
- `GET /api/referrals` → `{link:"https://t.me/<bot>?start=ref_<tg_id>", invited, bonus_days}`
- `POST /webhooks/{provider}` → `parse_webhook` → `mark_paid`; 200 всегда при валидной подписи (в т.ч. повтор), 403 при WebhookRejected
- `GET /sub/{token}` → `text/plain` base64, заголовки `Profile-Title`, `Subscription-Userinfo: upload=..; download=..; total=0; expire=<unix>`; 404 неизвестный токен; пустой список при истёкшей подписке.
- `main.py`: lifespan стартует бота и планировщик; `StaticFiles` из `webapp/dist` на `/`.

- [ ] Тесты (httpx AsyncClient, подписанный initData): без заголовка → 401; `/api/plans` содержит 4 тарифа и бейджи; trial дважды → 409; `/api/pay` lavatop без email → 400; повторный вебхук → 200 и одно продление; `/sub/{token}` с заголовком expire. FAIL → реализовать → PASS → Commit `feat: http api`

### Task 10: Бот, админка, планировщик

**Files:** Create `app/bot/setup.py`, `app/bot/start.py`, `app/bot/admin.py`, `app/bot/notify.py`, `app/scheduler.py`, `tests/test_scheduler.py`, `tests/test_admin.py`

**Interfaces:**
- `/start [ref_<tg_id>]` → создать пользователя, сообщение-приветствие + inline-кнопка `WebAppInfo(url=webapp_url)` «🚀 Открыть VPN»; также `set_chat_menu_button`.
- `/admin` (только `admin_ids`): кнопки «📊 Статистика» (всего, активные, за сегодня/месяц выручка по валютам), «🔎 Пользователь» (по tg_id/@username → срок, кнопки +7/+30 дней, отключить), «📣 Рассылка» (FSM: текст → подтверждение → отправка с паузой 0.05 с, подсчёт ошибок), «🖥 Серверы» (список, вкл/выкл, `/addserver` с JSON-параметрами).
- `scheduler.py` каждые 10 мин: `remind()` (3д/1д флаги), `expire()` (истёкшие → `upsert_client(enabled=False)` на всех серверах, уведомление один раз), `resync()` (`needs_sync=True` → `sync_user`).

- [ ] Тесты: `test_remind_3d_sent_once`; `test_expire_disables_not_deletes` (провайдер получил `enabled=False`, uuid прежний); `test_resync_clears_flag`; `test_admin_stats_counts`. FAIL → реализовать → PASS → Commit `feat: bot, admin, scheduler`

### Task 11: Мини-приложение

**Files:** Create `webapp/` (Vite React TS): `src/api.ts`, `src/App.tsx`, `src/screens/Home.tsx`, `Plans.tsx`, `Connect.tsx`, `Referral.tsx`, `src/components/*`, `src/styles.css`

**Экраны:**
- **Главная:** карточка статуса (активна до / осталось N дней / прогресс-бар; или «Нет подписки»), большая кнопка «Подключиться», кнопки «Продлить», «Пробный 3 дня» (если доступен), список локаций с флагами, «Пригласить друга», «Поддержка».
- **Тарифы:** 4 карточки (цена, ₽/мес, бейдж «−38% · Выгоднее всего»), выбор способа оплаты (Stars / Крипта / Карта·СБП), для карты — поле e-mail при первом разе; Stars → `openInvoice`, остальное → `openLink`; после возврата — опрос `/api/me` каждые 3 с до 2 мин.
- **Подключение:** выбор платформы (iOS/Android/Windows/macOS) → кнопка «Скачать приложение» (Happ/v2RayTun/Hiddify), «Добавить подписку» (deep-link `happ://add/<sub_url>` и аналоги), «Скопировать ссылку», QR (`qrcode.react`).
- **Рефералы:** ссылка, кнопка «Поделиться» (`shareURL`), счётчик приглашённых и бонусных дней.
- Тема из `themeParams` (CSS-переменные `--tg-theme-*`), `BackButton`, haptic на кнопках.

- [ ] `npm run build` без ошибок; `npx tsc --noEmit` чисто.
- [ ] Ручная проверка в браузере с моком `initData` (Playwright-скриншот главной и тарифов, 390×844).
- [ ] Commit `feat: telegram mini app`

### Task 12: Деплой и установка VPN-сервера

**Files:** Create `deploy/Dockerfile` (multi-stage: node build webapp → python), `deploy/docker-compose.yml` (app, postgres:16, caddy:2), `deploy/Caddyfile` (`{$DOMAIN} { reverse_proxy app:8000 }`), `deploy/.env.example`, `scripts/install_xui.sh`, `README.md`

- `install_xui.sh`: ставит 3x-ui официальным установщиком, генерирует Reality-ключи (`xray x25519`), создаёт inbound VLESS TCP Reality на 443 (sni `www.microsoft.com` по умолчанию, параметр), включает BBR, печатает JSON для `/addserver`.
- README (рус.): создание бота в @BotFather, включение Mini App, аренда VPS, установка сервера, настройка CryptoBot (вебхук `https://<домен>/webhooks/cryptobot`), lava.top (офферы на 4 тарифа, вебхук `https://<домен>/webhooks/lavatop`), запуск `docker compose up -d`, как добавить ЮKassa (шаблон модуля).

- [ ] `docker compose config` валиден; `bash -n scripts/install_xui.sh` ок; `docker build` проходит (если Docker доступен).
- [ ] Полный `pytest` зелёный.
- [ ] Commit `feat: deploy and server install script`
