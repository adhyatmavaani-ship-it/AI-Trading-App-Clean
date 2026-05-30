import { AnimatePresence, motion } from "framer-motion";

export function Toast({ message }: { message: string | null }) {
  return (
    <AnimatePresence>
      {message && (
        <motion.div
          className="fixed bottom-5 right-5 z-50 rounded-xl border border-primary/25 bg-surface px-4 py-3 text-sm font-semibold text-text shadow-glow"
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: 14 }}
        >
          {message}
        </motion.div>
      )}
    </AnimatePresence>
  );
}
