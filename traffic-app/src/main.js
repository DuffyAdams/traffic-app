import { mount } from "svelte";
import "./app.css";
import App from "./App.svelte";
import { initializeLocale } from "./utils/i18n.js";

initializeLocale();

const app = mount(App, {
  target: document.getElementById("app"),
});

export default app;
