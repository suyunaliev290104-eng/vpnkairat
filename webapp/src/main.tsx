import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./styles.css";
import { tg } from "./tg";

document.documentElement.dataset.theme = tg.colorScheme;
createRoot(document.getElementById("root")!).render(<StrictMode><App /></StrictMode>);
