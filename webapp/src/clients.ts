import type { Platform } from "./tg";

/* VPN client apps per platform. `id` must match DEEPLINKS in backend/app/api/sub.py.
   Store links: check before launch and update if an app moved. */
export interface ClientApp { id: string; name: string; store: string }

const HAPP = "Happ";
export const CLIENTS: Record<Platform, ClientApp[]> = {
  ios: [
    { id: "happ", name: HAPP, store: "https://apps.apple.com/app/happ-proxy-utility/id6504287215" },
    { id: "v2raytun", name: "v2RayTun", store: "https://apps.apple.com/app/v2raytun/id6476628951" },
  ],
  android: [
    { id: "happ", name: HAPP, store: "https://play.google.com/store/apps/details?id=com.happproxy" },
    { id: "v2raytun", name: "v2RayTun", store: "https://play.google.com/store/apps/details?id=com.v2raytun.android" },
  ],
  windows: [
    { id: "happ", name: HAPP, store: "https://github.com/Happ-proxy/happ-desktop/releases/latest" },
    { id: "hiddify", name: "Hiddify", store: "https://github.com/hiddify/hiddify-app/releases/latest" },
  ],
  macos: [
    { id: "happ", name: HAPP, store: "https://apps.apple.com/app/happ-proxy-utility/id6504287215" },
    { id: "hiddify", name: "Hiddify", store: "https://github.com/hiddify/hiddify-app/releases/latest" },
  ],
};

export const PLATFORM_NAMES: Record<Platform, string> = {
  ios: "iPhone", android: "Android", windows: "Windows", macos: "Mac",
};
