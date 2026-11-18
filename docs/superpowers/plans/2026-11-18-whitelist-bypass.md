# Обход белых списков + новые цены — Implementation Plan

> Inline execution. Spec: `docs/superpowers/specs/2026-11-18-vpn-telegram-design.md` (раздел «Дополнение»).

**Global constraints:** цены 199/549/999/1790 ₽, 190/520/950/1700⭐, 3/7/13/22 USDT; скидки 0/8/16/25%,
₽/мес 199/183/167/149; лимит обхода 5 ГиБ/сутки, сброс 00:00 Europe/Moscow.

### Task 1: Цены
`app/plans.py` — новые значения; тест `test_plans.py` обновить (сначала тест).

### Task 2: Модель и синхронизация bypass
- `Server.kind: str = "direct"`; `Settings.bypass_daily_gb = 5`.
- `ClientSpec.total_bytes: int`; `sync_user` ставит `bypass_daily_gb * 1024**3` для bypass, 0 для direct.
- `XuiProvider` шлёт `totalGB = spec.total_bytes`; `reset_traffic(server)` → `POST /panel/api/inbounds/resetAllClientTraffics/{inbound_id}`.
- Тесты: spec для bypass/direct; payload totalGB; reset endpoint.

### Task 3: Ссылки, планировщик, API
- `enabled_servers` сортирует direct → bypass; метка bypass `🛡 Обход · {name}`.
- `scheduler.reset_bypass(s, vpn)` — по всем enabled bypass-серверам; ошибки логируются. Cron 00:00 МСК.
- `/api/me`: `servers[].kind`, `bypass: {available, used_today, limit}`.
- `/addserver` принимает `kind`; список серверов в админке показывает 🛡.
- Тесты на всё перечисленное.

### Task 4: Мини-приложение и тексты
Блок «🛡 Обход белых списков» на главной (прогресс `x из 5 ГБ сегодня`, подсказка), локации без bypass,
шаг «Если мобильный интернет по белым спискам — выберите 🛡» в «Подключении»; убрать «от 99 ₽/мес»;
`/start` упоминает обход. `npm run build` + скриншот.

### Task 5: Скрипты и README
`install_xui.sh` создаёт relay-клиента и печатает его ссылку; новый `install_bypass.sh --exit-link --bot-ip`
(3x-ui, inbound Reality с SNI российского сайта, outbound → exit, TLS панели, ufw); README: раздел «Обход
белых списков», новые цены, офферы lava.top. `bash -n`.
