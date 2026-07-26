import React from "react";
import { ConsoleProvider } from "./state/consoleContext";
import { ConsoleShell } from "./ConsoleShell";

/**
 * console 子应用挂载入口（可嵌入组件，非 BrowserRouter 根组件）。
 *
 * 由主应用在 /console/* 嵌套路由下挂载，例如（编排者在 App.tsx 注册）：
 *
 *   const ConsoleApp = lazy(() => import("@/console/ConsoleApp"));
 *   ...
 *   <Route path="/console/*" element={<ConsoleApp />} />
 *
 * console 内部页面切换走自身状态机（consoleReducer 的 page/set），
 * 不占用 react-router 子路由，因此单个 /console/* 路由即可承载全部页面。
 */
export function ConsoleApp() {
  return (
    <ConsoleProvider>
      <ConsoleShell />
    </ConsoleProvider>
  );
}

export default ConsoleApp;
