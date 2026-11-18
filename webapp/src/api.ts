import { tg } from "./tg";

export interface Me {
  user: { tg_id: number; username: string | null; email: string | null };
  subscription: {
    active: boolean;
    expires_at: string | null;
    days_left: number;
    trial_available: boolean;
    sub_url: string;
    traffic_used: number;
    device_limit: number;
  };
  servers: { name: string; flag: string; country: string; kind: "direct" | "bypass" }[];
  bypass: { available: boolean; used_today: number; limit: number };
  support_username: string;
}

export interface Price { amount: number; currency: string }
export interface PlanDto {
  id: string; days: number; months: number; badge: string | null;
  discount: number; per_month_rub: number; prices: Record<string, Price>;
}
export interface ProviderDto { name: string; title: string; currency: string; kind: "link" | "invoice"; needs_email: boolean }
export interface PlansResp { plans: PlanDto[]; providers: ProviderDto[]; stars_shop_url: string }
export interface PayResp { payment_id: number; payment_url: string; kind: "link" | "invoice" }
export interface RefResp { link: string; invited: number; bonus_days: number }

export class ApiError extends Error {
  constructor(public status: number, public code: string) { super(code); }
}

async function req<T>(path: string, init: RequestInit = {}): Promise<T> {
  const r = await fetch(path, {
    ...init,
    headers: { "Content-Type": "application/json", Authorization: `tma ${tg.initData}`, ...(init.headers ?? {}) },
  });
  if (!r.ok) {
    let code = String(r.status);
    try { const j = await r.json(); if (typeof j.detail === "string") code = j.detail; } catch { /* empty */ }
    throw new ApiError(r.status, code);
  }
  return r.json();
}

export const api = {
  me: () => req<Me>("/api/me"),
  plans: () => req<PlansResp>("/api/plans"),
  trial: () => req<Me>("/api/trial", { method: "POST" }),
  pay: (plan_id: string, provider: string) =>
    req<PayResp>("/api/pay", { method: "POST", body: JSON.stringify({ plan_id, provider }) }),
  setEmail: (email: string) => req<Me>("/api/email", { method: "POST", body: JSON.stringify({ email }) }),
  referrals: () => req<RefResp>("/api/referrals"),
};

export const ERRORS: Record<string, string> = {
  trial_used: "Пробный период уже использован",
  email_required: "Укажите e-mail для чека",
  payment_provider_error: "Платёжная система не ответила, попробуйте позже или другой способ",
  unknown_provider: "Этот способ оплаты недоступен",
  "401": "Откройте приложение из Telegram",
};

export const errText = (e: unknown) =>
  e instanceof ApiError ? ERRORS[e.code] ?? "Что-то пошло не так" : "Нет соединения";
