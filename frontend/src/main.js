import "./assets/main.css";

import { createApp } from "vue";
import App from "./App.vue";

import Settings from "./components/pages/Settings.vue";
import AboutMain from "./components/pages/AboutMain.vue";
import WebshellEditorMain from "./components/pages/WebshellEditorMain.vue";
import HomeMain from "./components/pages/HomeMain.vue";
import TerminalMain from "./components/pages/TerminalMain.vue";
import ShellCommandMain from "./components/pages/ShellCommandMain.vue";
import FileBrowserMain from "./components/pages/FileBrowserMain.vue";
import PhpEvalMain from "./components/pages/PhpEvalMain.vue";
import EmulatedAntswordMain from "./components/pages/EmulatedAntswordMain.vue";
import BasicInfoMain from "./components/pages/BasicInfoMain.vue";
import AwdActionsMain from "./components/pages/AwdToolsMain.vue";
import Proxies from "./components/pages/Proxies.vue";
import { createRouter, createWebHashHistory } from "vue-router";
import { getCurrentApiUrl } from "./assets/utils";
import Terminal from "vue-web-terminal";
//  亮色主题：vue-web-terminal/lib/theme/light.css
import "./assets/vue-web-terminal.css";
import ReverseShellMain from "./components/pages/ReverseShellMain.vue";
import ConnectorMain from "./components/pages/ConnectorMain.vue";
import ConnectorEditorMain from "./components/pages/ConnectorEditorMain.vue";
import LoginMain from "./components/pages/LoginMain.vue";
import DBMSMain from "./components/pages/DBMSMain.vue";
import DBMSList from "./components/pages/DBMSList.vue";
import DBMSDetail from "./components/pages/DBMSDetail.vue";

const routes = [
  { path: "/login", component: LoginMain, props: true },
  { path: "/", component: HomeMain, props: true },
  {
    path: "/webshell-editor/:session",
    component: WebshellEditorMain,
    props: true,
  },
  {
    path: "/webshell-editor/",
    component: WebshellEditorMain,
    props: true,
  },
  {
    path: "/settings/",
    component: Settings,
    props: true,
  },
  {
    path: "/connector/",
    component: ConnectorMain,
    props: true,
  },
  {
    path: "/connector-editor/:connector",
    component: ConnectorEditorMain,
    props: true,
  },
  {
    path: "/connector-editor/",
    component: ConnectorEditorMain,
    props: true,
  },
  {
    path: "/about/",
    component: AboutMain,
    props: true,
  },
  {
    path: "/terminal/:session",
    component: TerminalMain,
    props: (route) => ({
      session: route.params.session,
      pwd: route.query.pwd,
    }),
  },
  { path: "/shell-command/:session", component: ShellCommandMain, props: true },
  { path: "/awd-tools/:session", component: AwdActionsMain, props: true },
  { path: "/file-browser/:session", component: FileBrowserMain, props: true },
  { path: "/php-eval/:session", component: PhpEvalMain, props: true },
  {
    path: "/emulated-antsword/:session",
    component: EmulatedAntswordMain,
    props: true,
  },
  { path: "/basic-info/:session", component: BasicInfoMain, props: true },
  { path: "/reverse-shell/:session", component: ReverseShellMain, props: true },
  { path: "/proxies", component: Proxies, props: true },
  { path: "/proxies/:session", component: Proxies, props: true },
  { path: "/dbms/", component: DBMSList, props: true },
  { path: "/dbms/:id", component: DBMSDetail, props: true },
];

const router = createRouter({
  history: createWebHashHistory(),
  routes,
});

router.beforeEach(async (to, from, next) => {
  try {
    const resp = await fetch(`${getCurrentApiUrl()}/auth/status`);
    const data = await resp.json();
    const ok = data?.data === true;
    if (!ok && to.path !== "/login") {
      next("/login");
      return;
    }
    if (ok && to.path === "/login") {
      next("/");
      return;
    }
    next();
  } catch {
    next();
  }
});
createApp(App).use(router).use(Terminal).mount("#app");
