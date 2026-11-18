#!/usr/bin/env bash
# Устанавливает 3x-ui + inbound VLESS/Reality на чистый Ubuntu/Debian VPS
# и печатает команду /addserver для бота.
#
# Два режима:
#  • Обычная локация (зарубежный VPS) — также создаёт relay-клиента и печатает его ссылку:
#      bash install_xui.sh --bot-ip 1.2.3.4 --name "Нидерланды" --flag 🇳🇱
#  • Обход белых списков (VPS в РФ на IP из белого списка) — весь трафик уходит на зарубежный выход:
#      bash install_xui.sh --bot-ip 1.2.3.4 --name "Москва" --flag 🇷🇺 --exit-link "vless://...relay..."
#
# Опции: --bot-ip IP (обязательно: IP сервера с ботом — только ему открывается панель)
#        --name NAME  --flag EMOJI  --port 443
#        --sni DOMAIN  сайт для маскировки (по умолчанию www.microsoft.com; в режиме обхода — ya.ru,
#                      берите сайт, который точно есть в белом списке вашего оператора)
#        --exit-link LINK  relay-ссылка зарубежного выхода → режим обхода белых списков
set -euo pipefail

NAME="Server"; FLAG="🌐"; SNI=""; PORT=443; BOT_IP=""; EXIT_LINK=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --name) NAME="$2"; shift 2;;
    --flag) FLAG="$2"; shift 2;;
    --sni)  SNI="$2"; shift 2;;
    --port) PORT="$2"; shift 2;;
    --bot-ip) BOT_IP="$2"; shift 2;;
    --exit-link) EXIT_LINK="$2"; shift 2;;
    *) echo "unknown option $1"; exit 1;;
  esac
done
[[ $EUID -eq 0 ]] || { echo "Запустите от root (sudo)"; exit 1; }
[[ -n "$BOT_IP" ]] || { echo "Укажите --bot-ip <IP сервера с ботом>"; exit 1; }
if [[ -n "$EXIT_LINK" ]]; then
  KIND=bypass; SNI="${SNI:-ya.ru}"
  [[ "$EXIT_LINK" == vless://* ]] || { echo "--exit-link должен начинаться с vless://"; exit 1; }
else
  KIND=direct; SNI="${SNI:-www.microsoft.com}"
fi

apt-get update -qq && apt-get install -y -qq curl jq openssl ufw >/dev/null

PANEL_USER="admin$(openssl rand -hex 3)"
PANEL_PASS="$(openssl rand -hex 12)"
PANEL_PORT=$(( 20000 + RANDOM % 20000 ))
PANEL_PATH="$(openssl rand -hex 8)"
HOST="$(curl -fsS https://api.ipify.org)"

echo "==> Устанавливаю 3x-ui"
# Официальный установщик; на вопросы отвечаем «нет» — настройки зададим сами ниже.
yes n | bash <(curl -Ls https://raw.githubusercontent.com/mhsanaei/3x-ui/master/install.sh) || true
x-ui setting -username "$PANEL_USER" -password "$PANEL_PASS" -port "$PANEL_PORT" -webBasePath "$PANEL_PATH" >/dev/null

echo "==> HTTPS для панели (самоподписанный сертификат, бот его закрепляет)"
CERT_DIR=/etc/x-ui-cert; mkdir -p "$CERT_DIR"
openssl req -x509 -newkey rsa:2048 -nodes -days 3650 -subj "/CN=${HOST}" \
  -addext "subjectAltName=IP:${HOST}" -keyout "$CERT_DIR/key.pem" -out "$CERT_DIR/cert.pem" 2>/dev/null
x-ui cert -webCert "$CERT_DIR/cert.pem" -webCertKey "$CERT_DIR/key.pem" >/dev/null 2>&1 \
  || x-ui setting -webCert "$CERT_DIR/cert.pem" -webCertKey "$CERT_DIR/key.pem" >/dev/null
x-ui restart >/dev/null; sleep 3

echo "==> Фаервол: SSH и VPN открыты всем, панель — только боту ($BOT_IP)"
ufw allow 22/tcp >/dev/null
ufw allow "${PORT}/tcp" >/dev/null
ufw allow from "$BOT_IP" to any port "$PANEL_PORT" proto tcp >/dev/null
ufw --force enable >/dev/null

echo "==> Включаю BBR"
grep -q "tcp_congestion_control=bbr" /etc/sysctl.conf || {
  echo "net.core.default_qdisc=fq" >> /etc/sysctl.conf
  echo "net.ipv4.tcp_congestion_control=bbr" >> /etc/sysctl.conf
  sysctl -p >/dev/null
}

echo "==> Генерирую ключи Reality"
XRAY="$(ls /usr/local/x-ui/bin/xray-linux-* | head -1)"
KEYS="$("$XRAY" x25519)"
PRIV="$(echo "$KEYS" | grep -iE '^private' | awk -F': ' '{print $2}' | tr -d ' ')"
PUB="$(echo "$KEYS" | grep -iE '^(public key|password)' | awk -F': ' '{print $2}' | tr -d ' ')"
SID="$(openssl rand -hex 4)"

PANEL="https://127.0.0.1:${PANEL_PORT}/${PANEL_PATH}"
JAR="$(mktemp)"
curl -fsSk -c "$JAR" -X POST "$PANEL/login" -d "username=$PANEL_USER&password=$PANEL_PASS" | jq -e .success >/dev/null

SETTINGS='{"clients":[],"decryption":"none","fallbacks":[]}'
STREAM=$(jq -nc --arg sni "$SNI" --arg priv "$PRIV" --arg pub "$PUB" --arg sid "$SID" '{
  network:"tcp", security:"reality",
  realitySettings:{show:false, xver:0, dest:($sni+":443"), serverNames:[$sni], privateKey:$priv,
                   shortIds:[$sid], settings:{publicKey:$pub, fingerprint:"chrome", serverName:"", spiderX:"/"}},
  tcpSettings:{acceptProxyProtocol:false, header:{type:"none"}}}')
SNIFF='{"enabled":true,"destOverride":["http","tls","quic"]}'

echo "==> Создаю inbound VLESS Reality на порту $PORT"
RESP=$(curl -fsSk -b "$JAR" -X POST "$PANEL/panel/api/inbounds/add" \
  --data-urlencode "remark=vless-reality" --data-urlencode "enable=true" --data-urlencode "port=$PORT" \
  --data-urlencode "protocol=vless" --data-urlencode "settings=$SETTINGS" \
  --data-urlencode "streamSettings=$STREAM" --data-urlencode "sniffing=$SNIFF" \
  --data-urlencode "expiryTime=0" --data-urlencode "total=0" --data-urlencode "up=0" --data-urlencode "down=0")
echo "$RESP" | jq -e .success >/dev/null || { echo "Ошибка создания inbound: $RESP"; exit 1; }
INBOUND_ID=$(echo "$RESP" | jq .obj.id)

RELAY_LINK=""
if [[ "$KIND" == direct ]]; then
  echo "==> Создаю relay-клиента для будущих серверов обхода белых списков"
  RUUID="$(cat /proc/sys/kernel/random/uuid)"
  RCLIENT=$(jq -nc --arg id "$RUUID" --arg email "relay-$(openssl rand -hex 3)" \
    '{clients:[{id:$id, email:$email, flow:"xtls-rprx-vision", limitIp:0, totalGB:0, expiryTime:0,
                enable:true, subId:"", tgId:"", reset:0}]}')
  curl -fsSk -b "$JAR" -X POST "$PANEL/panel/api/inbounds/addClient" \
    -H "Content-Type: application/json" -d "$(jq -nc --argjson id "$INBOUND_ID" --arg s "$RCLIENT" '{id:$id, settings:$s}')" \
    | jq -e .success >/dev/null
  RELAY_LINK="vless://${RUUID}@${HOST}:${PORT}?type=tcp&security=reality&pbk=${PUB}&fp=chrome&sni=${SNI}&sid=${SID}&flow=xtls-rprx-vision#relay"
else
  echo "==> Направляю весь трафик на зарубежный выход"
  rest="${EXIT_LINK#vless://}"; rest="${rest%%#*}"
  E_UUID="${rest%%@*}"; hp="${rest#*@}"; hp="${hp%%\?*}"; E_HOST="${hp%:*}"; E_PORT="${hp##*:}"
  Q="${rest#*\?}"
  qp() { echo "$Q" | tr '&' '\n' | grep "^$1=" | head -1 | cut -d= -f2-; }
  OUT=$(jq -nc --arg addr "$E_HOST" --argjson port "$E_PORT" --arg id "$E_UUID" --arg flow "$(qp flow)" \
    --arg sni "$(qp sni)" --arg pbk "$(qp pbk)" --arg sid "$(qp sid)" '{
      tag:"exit", protocol:"vless",
      settings:{vnext:[{address:$addr, port:$port, users:[{id:$id, encryption:"none", flow:$flow}]}]},
      streamSettings:{network:"tcp", security:"reality",
        realitySettings:{serverName:$sni, fingerprint:"chrome", publicKey:$pbk, shortId:$sid, spiderX:"/"}}}')
  CUR=$(curl -fsSk -b "$JAR" -X POST "$PANEL/panel/xray/" | jq -r .obj | jq -c .xraySetting)
  # Первый outbound — маршрут по умолчанию: ставим «exit» первым, остальные (direct, blocked) оставляем.
  NEW=$(echo "$CUR" | jq -c --argjson out "$OUT" '.outbounds = [$out] + ((.outbounds // []) | map(select(.tag != "exit")))')
  curl -fsSk -b "$JAR" -X POST "$PANEL/panel/xray/update" --data-urlencode "xraySetting=$NEW" | jq -e .success >/dev/null
  curl -fsSk -b "$JAR" -X POST "$PANEL/panel/api/server/restartXrayService" >/dev/null || x-ui restart >/dev/null
fi
rm -f "$JAR"

JSON=$(jq -nc --arg name "$NAME" --arg flag "$FLAG" --arg url "https://${HOST}:${PANEL_PORT}/${PANEL_PATH}" \
  --arg u "$PANEL_USER" --arg p "$PANEL_PASS" --argjson id "$INBOUND_ID" --arg host "$HOST" --argjson port "$PORT" \
  --arg pbk "$PUB" --arg sni "$SNI" --arg sid "$SID" --rawfile cert "$CERT_DIR/cert.pem" --arg kind "$KIND" \
  '{name:$name, flag:$flag, panel_url:$url, username:$u, password:$p, inbound_id:$id, host:$host, port:$port,
    reality_pbk:$pbk, reality_sni:$sni, reality_sid:$sid, panel_cert:$cert, kind:$kind}')

cat <<MSG

✅ Готово!

Панель 3x-ui:  https://${HOST}:${PANEL_PORT}/${PANEL_PATH}
Логин/пароль:  ${PANEL_USER} / ${PANEL_PASS}

Панель открыта только с IP бота ($BOT_IP). Зайти самому: ssh -L ${PANEL_PORT}:127.0.0.1:${PANEL_PORT} root@${HOST}
и откройте https://127.0.0.1:${PANEL_PORT}/${PANEL_PATH} (браузер предупредит о сертификате — это нормально).

Отправьте боту (вы должны быть в ADMIN_IDS):

/addserver ${JSON}

MSG

if [[ -n "$RELAY_LINK" ]]; then
  cat <<MSG
Relay-ссылка этого сервера (для серверов обхода белых списков, храните в секрете):

$RELAY_LINK

MSG
fi
