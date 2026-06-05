"use client";

import { createContext, useCallback, useContext, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { cn } from "@/lib/utils";

type ToastVariant = "default" | "success" | "error" | "warning";

interface ToastItem {
  id: number;
  message: string;
  variant: ToastVariant;
}

interface ToastContextValue {
  toast: (message: string, variant?: ToastVariant) => void;
}

const ToastContext = createContext<ToastContextValue>({ toast: () => {} });

let counter = 0;

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);

  const toast = useCallback((message: string, variant: ToastVariant = "default") => {
    const id = ++counter;
    setItems((prev) => [...prev, { id, message, variant }]);
    setTimeout(() => setItems((prev) => prev.filter((t) => t.id !== id)), 4000);
  }, []);

  const dismiss = (id: number) => setItems((prev) => prev.filter((t) => t.id !== id));

  const variantStyles: Record<ToastVariant, string> = {
    default: "bg-elevated border-line text-fg",
    success: "bg-elevated border-[hsl(var(--pitch)/0.5)] text-fg",
    error: "bg-elevated border-[hsl(var(--signal)/0.5)] text-fg",
    warning: "bg-elevated border-[hsl(45_95%_58%/0.5)] text-fg",
  };

  const icons: Record<ToastVariant, string> = {
    default: "●",
    success: "✓",
    error: "✕",
    warning: "⚠",
  };

  const iconColors: Record<ToastVariant, string> = {
    default: "text-muted",
    success: "text-pitch",
    error: "text-signal",
    warning: "text-[hsl(45_95%_58%)]",
  };

  return (
    <ToastContext.Provider value={{ toast }}>
      {children}
      <div className="fixed bottom-5 right-5 z-[9999] flex flex-col gap-2 max-w-sm w-full pointer-events-none">
        <AnimatePresence mode="popLayout">
          {items.map((item) => (
            <motion.div
              key={item.id}
              initial={{ opacity: 0, y: 20, scale: 0.95 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95, transition: { duration: 0.15 } }}
              className={cn(
                "pointer-events-auto flex items-center gap-3 px-4 py-3 rounded-lg border text-sm",
                "shadow-lg backdrop-blur-sm cursor-pointer",
                variantStyles[item.variant],
              )}
              onClick={() => dismiss(item.id)}
            >
              <span className={cn("text-xs font-bold shrink-0", iconColors[item.variant])}>
                {icons[item.variant]}
              </span>
              <span className="flex-1">{item.message}</span>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  return useContext(ToastContext);
}
