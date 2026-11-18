#!/usr/bin/env bash
# Устанавливает 3x-ui + inbound VLESS/Reality на чистый Ubuntu/Debian VPS
# и печатает команду /addserver для бота.
#
#   curl -fsSL <raw-url>/install_xui.sh | sudo bash -s -- --name "Нидерланды" --flag 🇳🇱
#
# Опции: --name NAME  --flag EMOJI  --sni DOMAIN (по умолчанию www.microsoft.com)  --port 443
set -euo pipefail

NAME="Server"; FLAG="🌐"; SNI="www.microsoft.com"; PORT=443
while [[ $# -gt 0 ]]; do
  case "$1" in
    --name) NAME="$2"; shift 2;;
    --flag) FLAG="$2"; shift 2;;
    --sni)  SNI="$2"; shift 2;;
    --port) PORT="$2"; shift 2;;
    *) echo "unknown option $1"; exit 1;;
  esac
done
[[ $EUID -eq 0 ]] || { echo "Запустите от root (sudo)"; exit 1; }

apt-get update -qq && apt-get install -y -qq curl jq openssl >/dev/null

PANEL_USER="admin$(openssl rand -hex 3)"
PANEL_PASS="$(openssl rand -hex 12)"
PANEL_PORT=$(( 20000 + RANDOM % 20000 ))
PANEL_PATH="$(openssl rand -hex 8)"
HOST="$(curl -fsS https://api.ipify.org)"

echo "==> Устанавливаю 3x-ui"
# Официальный установщик; на вопросы отвечаем «нет» — настройки зададим сами ниже.
yes n | bash <(curl -Ls https://raw.githubusercontent.com/mhsanaei/3x-ui/master/install.sh) || true
x-ui setting -username "$PANEL_USER" -password "$PANEL_PASS" -port "$PANEL_PORT" -webBasePath "$PANEL_PATH" >/dev/null
x-ui restart >/dev/null; sleep 3

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

PANEL="http://127.0.0.1:${PANEL_PORT}/${PANEL_PATH}"
JAR="$(mktemp)"
curl -fsS -c "$JAR" -X POST "$PANEL/login" -d "username=$PANEL_USER&password=$PANEL_PASS" | jq -e .success >/dev/null

SETTINGS='{"clients":[],"decryption":"none","fallbacks":[]}'
STREAM=$(jq -nc --arg sni "$SNI" --arg priv "$PRIV" --arg pub "$PUB" --arg sid "$SID" '{
  network:"tcp", security:"reality",
  realitySettings:{show:false, xver:0, dest:($sni+":443"), serverNames:[$sni], privateKey:$priv,
                   shortIds:[$sid], settings:{publicKey:$pub, fingerprint:"chrome", serverName:"", spiderX:"/"}},
  tcpSettings:{acceptProxyProtocol:false, header:{type:"none"}}}')
SNIFF='{"enabled":true,"destOverride":["http","tls","quic"]}'

echo "==> Создаю inbound VLESS Reality на порту $PORT"
RESP=$(curl -fsS -b "$JAR" -X POST "$PANEL/panel/api/inbounds/add" \
  --data-urlencode "remark=vless-reality" --data-urlencode "enable=true" --data-urlencode "port=$PORT" \
  --data-urlencode "protocol=vless" --data-urlencode "settings=$SETTINGS" \
  --data-urlencode "streamSettings=$STREAM" --data-urlencode "sniffing=$SNIFF" \
  --data-urlencode "expiryTime=0" --data-urlencode "total=0" --data-urlencode "up=0" --data-urlencode "down=0")
echo "$RESP" | jq -e .success >/dev/null || { echo "Ошибка создания inbound: $RESP"; exit 1; }
INBOUND_ID=$(echo "$RESP" | jq .obj.id)
rm -f "$JAR"

# Порт панели открыт только для вашего бот-сервера — ограничьте его фаерволом при желании:
#   ufw allow from <IP_бота> to any port $PANEL_PORT
JSON=$(jq -nc --arg name "$NAME" --arg flag "$FLAG" --arg url "http://${HOST}:${PANEL_PORT}/${PANEL_PATH}" \
  --arg u "$PANEL_USER" --arg p "$PANEL_PASS" --argjson id "$INBOUND_ID" --arg host "$HOST" --argjson port "$PORT" \
  --arg pbk "$PUB" --arg sni "$SNI" --arg sid "$SID" \
  '{name:$name, flag:$flag, panel_url:$url, username:$u, password:$p, inbound_id:$id, host:$host, port:$port,
    reality_pbk:$pbk, reality_sni:$sni, reality_sid:$sid}')

cat <<MSG

✅ Готово!

Панель 3x-ui:  http://${HOST}:${PANEL_PORT}/${PANEL_PATH}
Логин/пароль:  ${PANEL_USER} / ${PANEL_PASS}

Отправьте боту (вы должны быть в ADMIN_IDS):

/addserver ${JSON}

MSG
