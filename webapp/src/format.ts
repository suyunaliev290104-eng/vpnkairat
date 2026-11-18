export const fmtDate = (iso: string) =>
  new Date(iso).toLocaleDateString("ru-RU", { day: "numeric", month: "long", year: "numeric" });

export function plural(n: number, one: string, few: string, many: string) {
  const m10 = n % 10, m100 = n % 100;
  if (m10 === 1 && m100 !== 11) return one;
  if (m10 >= 2 && m10 <= 4 && (m100 < 12 || m100 > 14)) return few;
  return many;
}

export const days = (n: number) => `${n} ${plural(n, "день", "дня", "дней")}`;
export const months = (n: number) => `${n} ${plural(n, "месяц", "месяца", "месяцев")}`;

export function fmtBytes(b: number) {
  if (b < 1024 ** 2) return `${(b / 1024).toFixed(0)} КБ`;
  if (b < 1024 ** 3) return `${(b / 1024 ** 2).toFixed(0)} МБ`;
  return `${(b / 1024 ** 3).toFixed(1)} ГБ`;
}

const CUR: Record<string, string> = { RUB: "₽", XTR: "⭐", USDT: "USDT" };
export const fmtPrice = (amount: number, currency: string) =>
  currency === "XTR" ? `${amount} ⭐` : `${amount} ${CUR[currency] ?? currency}`;
