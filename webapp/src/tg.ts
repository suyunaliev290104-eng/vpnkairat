/* Thin typed wrapper over window.Telegram.WebApp with a browser fallback for local dev. */
type Haptic = "light" | "medium" | "heavy" | "rigid" | "soft";

interface WebApp {
  initData: string;
  colorScheme: "light" | "dark";
  ready(): void;
  expand(): void;
  openLink(url: string): void;
  openTelegramLink(url: string): void;
  openInvoice(url: string, cb?: (status: string) => void): void;
  showAlert(msg: string): void;
  BackButton: { show(): void; hide(): void; onClick(cb: () => void): void; offClick(cb: () => void): void };
  HapticFeedback: { impactOccurred(s: Haptic): void; notificationOccurred(t: "success" | "error" | "warning"): void };
}

declare global {
  interface Window { Telegram?: { WebApp: WebApp } }
}

const noop = () => {};
const fallback: WebApp = {
  initData: new URLSearchParams(location.search).get("initData") ?? "",
  colorScheme: matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light",
  ready: noop,
  expand: noop,
  openLink: (u) => window.open(u, "_blank"),
  openTelegramLink: (u) => window.open(u, "_blank"),
  openInvoice: (u) => window.open(u, "_blank"),
  showAlert: (m) => alert(m),
  BackButton: { show: noop, hide: noop, onClick: noop, offClick: noop },
  HapticFeedback: { impactOccurred: noop, notificationOccurred: noop },
};

export const tg: WebApp = window.Telegram?.WebApp?.initData ? window.Telegram.WebApp : fallback;

export const haptic = (s: Haptic = "light") => tg.HapticFeedback.impactOccurred(s);

export type Platform = "ios" | "android" | "windows" | "macos";

export function detectPlatform(): Platform {
  const ua = navigator.userAgent.toLowerCase();
  if (/iphone|ipad|ipod/.test(ua)) return "ios";
  if (/android/.test(ua)) return "android";
  if (/mac os/.test(ua)) return "macos";
  return "windows";
}
