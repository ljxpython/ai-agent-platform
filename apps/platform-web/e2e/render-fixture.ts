import { createApp } from "vue";
import i18n from "../src/i18n";
import Fixture from "./render-fixture.vue";
import "../src/styles/index.css";
createApp(Fixture).use(i18n).mount("#app");
