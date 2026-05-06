"use client";

import * as React from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Quote, Sparkles, Languages, Send } from "lucide-react";
import { Button } from "@/components/ui/button";

interface FloatingMenuProps {
    position: { x: number; y: number } | null;
    selectedText: string;
    onAction: (action: "quote" | "summarize" | "translate" | "send") => void;
}

export function FloatingMenu({ position, selectedText, onAction }: FloatingMenuProps) {
    if (!position) return null;

    return (
        <AnimatePresence>
            <motion.div
                initial={{ opacity: 0, scale: 0.9, y: 10 }}
                animate={{ opacity: 1, scale: 1, y: 0 }}
                exit={{ opacity: 0, scale: 0.9, y: 10 }}
                style={{
                    position: "fixed",
                    left: position.x,
                    top: position.y,
                    transform: "translate(-50%, -100%)",
                    zIndex: 100,
                }}
                className="flex items-center gap-1 p-1 bg-zinc-900/90 dark:bg-zinc-100/90 backdrop-blur-md rounded-full shadow-xl border border-zinc-500/20 mb-3"
            >
                <MenuButton
                    icon={<Quote className="h-4 w-4" />}
                    label="Quote"
                    onClick={() => onAction("quote")}
                />
                <MenuButton
                    icon={<Sparkles className="h-4 w-4" />}
                    label="Summarize"
                    onClick={() => onAction("summarize")}
                />
                <MenuButton
                    icon={<Languages className="h-4 w-4" />}
                    label="Translate"
                    onClick={() => onAction("translate")}
                />
                <div className="w-[1px] h-4 bg-zinc-500/30 mx-1" />
                <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8 rounded-full bg-blue-600 hover:bg-blue-500 text-white transition-colors"
                    onClick={() => onAction("send")}
                >
                    <Send className="h-4 w-4" />
                </Button>
            </motion.div>
        </AnimatePresence>
    );
}

function MenuButton({ icon, label, onClick }: { icon: React.ReactNode; label: string; onClick: () => void }) {
    return (
        <Button
            variant="ghost"
            size="sm"
            className="h-8 gap-2 rounded-full text-zinc-300 hover:text-white dark:text-zinc-600 dark:hover:text-black hover:bg-white/10 dark:hover:bg-black/10 transition-all font-medium text-xs px-3"
            onClick={onClick}
        >
            {icon}
            <span>{label}</span>
        </Button>
    );
}
