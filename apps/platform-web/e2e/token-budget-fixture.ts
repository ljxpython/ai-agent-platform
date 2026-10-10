import { createApp } from "vue";
import { createPinia } from "pinia";
import i18n from "../src/i18n";
import Fixture from "./token-budget-fixture.vue";
import "../src/styles/index.css";

const app = createApp(Fixture);
app.use(createPinia());
app.use(i18n);
app.mount("#app");
