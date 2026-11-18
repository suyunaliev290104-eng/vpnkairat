import { useCallback, useEffect, useState } from "react";
import { api, errText, type Me } from "./api";
import { Loader } from "./components/ui";
import { Connect } from "./screens/Connect";
import { Home } from "./screens/Home";
import { Plans } from "./screens/Plans";
import { Referral } from "./screens/Referral";
import { tg } from "./tg";

export type Screen = "home" | "plans" | "connect" | "referral";

export default function App() {
  const [me, setMe] = useState<Me | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [screen, setScreen] = useState<Screen>("home");

  const load = useCallback(() => {
    setError(null);
    api.me().then(setMe).catch((e) => setError(errText(e)));
  }, []);

  useEffect(() => { tg.ready(); tg.expand(); load(); }, [load]);

  useEffect(() => {
    const back = () => setScreen("home");
    if (screen === "home") tg.BackButton.hide();
    else tg.BackButton.show();
    tg.BackButton.onClick(back);
    window.scrollTo(0, 0);
    return () => tg.BackButton.offClick(back);
  }, [screen]);

  if (error) {
    return (
      <div className="screen center-col">
        <h2>😕 {error}</h2>
        <button className="btn btn-primary" onClick={load}>Повторить</button>
      </div>
    );
  }
  if (!me) return <Loader />;

  return (
    <>
      {screen === "home" && <Home me={me} setMe={setMe} go={setScreen} />}
      {screen === "plans" && <Plans me={me} setMe={setMe} onPaid={() => setScreen("connect")} />}
      {screen === "connect" && <Connect me={me} go={setScreen} />}
      {screen === "referral" && <Referral />}
    </>
  );
}
