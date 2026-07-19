import React, { createContext, useContext, useMemo, useReducer } from "react";
import { consoleReducer, createInitialConsoleState, type ConsoleAction, type ConsoleState } from "./consoleReducer";

const ConsoleStateContext = createContext<ConsoleState | null>(null);
const ConsoleDispatchContext = createContext<React.Dispatch<ConsoleAction> | null>(null);

export function ConsoleProvider({ children }: { children: React.ReactNode }) {
  const [state, dispatch] = useReducer(consoleReducer, undefined, createInitialConsoleState);
  const memoizedState = useMemo(() => state, [state]);

  return (
    <ConsoleStateContext.Provider value={memoizedState}>
      <ConsoleDispatchContext.Provider value={dispatch}>{children}</ConsoleDispatchContext.Provider>
    </ConsoleStateContext.Provider>
  );
}

export function useConsoleState(): ConsoleState {
  const value = useContext(ConsoleStateContext);
  if (!value) {
    throw new Error("useConsoleState must be used within ConsoleProvider");
  }
  return value;
}

export function useConsoleDispatch(): React.Dispatch<ConsoleAction> {
  const value = useContext(ConsoleDispatchContext);
  if (!value) {
    throw new Error("useConsoleDispatch must be used within ConsoleProvider");
  }
  return value;
}
