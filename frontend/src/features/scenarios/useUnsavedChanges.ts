import { useEffect, useRef } from "react";
import { useBlocker } from "react-router-dom";

export function useUnsavedChanges(isDirty: boolean) {
  const blocker = useBlocker(isDirty);
  const dialogRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (blocker.state !== "blocked") return;
    const previous = document.activeElement as HTMLElement | null;
    dialogRef.current?.querySelector("button")?.focus();
    return () => {
      if (previous?.isConnected) previous.focus();
    };
  }, [blocker.state]);
  useEffect(() => {
    const warn = (event: BeforeUnloadEvent) => {
      if (isDirty) {
        event.preventDefault();
        event.returnValue = "";
      }
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [isDirty]);
  return { blocker, dialogRef };
}
