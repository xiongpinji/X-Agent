import React from "react";

export type ConsoleLayoutProps = {
  sidebar: React.ReactNode;
  topBar: React.ReactNode;
  mainArea: React.ReactNode;
  contextPanel: React.ReactNode;
  statusBar: React.ReactNode;
  className?: string;
};

export function ConsoleLayout(props: ConsoleLayoutProps) {
  return (
    <div className={["min-h-screen bg-slate-100", props.className].filter(Boolean).join(" ")}>
      <div className="grid min-h-screen grid-cols-[280px_minmax(0,1fr)_320px] grid-rows-[64px_minmax(0,1fr)_44px]">
        <aside className="row-span-3 border-r bg-white">{props.sidebar}</aside>
        <header className="col-start-2 row-start-1 border-b bg-white">{props.topBar}</header>
        <main className="col-start-2 row-start-2 overflow-auto p-4">
          <div className="mx-auto w-full max-w-[1600px]">{props.mainArea}</div>
        </main>
        <aside className="col-start-3 row-start-1 row-span-2 border-l bg-white">{props.contextPanel}</aside>
        <footer className="col-start-2 row-start-3 border-t bg-white">{props.statusBar}</footer>
      </div>
    </div>
  );
}
