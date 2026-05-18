import { createApp } from "vue";
import { createPinia } from "pinia";
import ElementPlus from "element-plus";
import "element-plus/dist/index.css";

import App from "./App.vue";
import { queryClient, vueQueryPlugin } from "./app/providers/query-client";
import router from "./router";
import "./styles/index.css";

// 应用入口只负责装配运行时能力，不承载业务初始化逻辑。
const app = createApp(App);

app.use(createPinia());
app.use(router);
app.use(ElementPlus);
app.use(vueQueryPlugin, { queryClient });

app.mount("#app");
