"use client";

import React from "react";
import { MessageItem } from "./message-item";
import { motion, AnimatePresence } from "framer-motion";

interface Message {
    id: string;
    role: "user" | "assistant";
    content: string;
    citations?: Array<{ id: number; source: string; page?: number; content?: string; summary?: string }>;
    isStreaming?: boolean;
    isThinking?: boolean;
}

interface ChatAreaProps {
    messages: Message[];
}

export function ChatArea({ messages }: ChatAreaProps) {
    const scrollRef = React.useRef<HTMLDivElement>(null);
    const bottomRef = React.useRef<HTMLDivElement>(null);

    // Auto-scroll to bottom
    React.useEffect(() => {
        if (bottomRef.current) {
            // Dùng 'auto' thay vì 'smooth' để tránh bị "nhảy" màn hình trên iPhone khi load lại trang
            bottomRef.current.scrollIntoView({ behavior: messages.length <= 1 ? "auto" : "smooth" });
        }
    }, [messages]);

    return (
        <div
            ref={scrollRef}
            className="flex-1 w-full overflow-y-auto relative"
        >
            <div className="max-w-4xl mx-auto flex flex-col h-full pt-8 pb-32 px-4">
                <AnimatePresence mode="wait">
                    {messages.length > 0 ? (
                        <motion.div
                            key="messages-list"
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            exit={{ opacity: 0 }}
                            className="space-y-2"
                        >
                            {messages.map((message) => (
                                <motion.div
                                    key={message.id}
                                    initial={{ opacity: 0, y: 10 }}
                                    animate={{ opacity: 1, y: 0 }}
                                    transition={{ duration: 0.3 }}
                                >
                                    <MessageItem
                                        role={message.role}
                                        content={message.content}
                                        citations={message.citations}
                                        isStreaming={message.isStreaming}
                                        isThinking={message.isThinking}
                                    />
                                </motion.div>
                            ))}
                        </motion.div>
                    ) : (
                        <motion.div
                            key="welcome-screen"
                            initial={{ opacity: 0, y: 20 }}
                            animate={{ opacity: 1, y: 0 }}
                            exit={{ opacity: 0, y: -20 }}
                            className="flex-1 flex flex-col items-center justify-center p-8 text-center space-y-8"
                        >
                            <motion.div
                                initial={{ scale: 0.8, opacity: 0 }}
                                animate={{ scale: 1, opacity: 1 }}
                                transition={{ duration: 0.5, type: "spring" }}
                                className="h-20 w-20 md:h-28 md:w-28 rounded-[1.5rem] md:rounded-[2rem] bg-gradient-to-br from-blue-600 via-indigo-600 to-purple-600 flex items-center justify-center shadow-2xl rotate-3 relative group"
                            >
                                <div className="absolute inset-0 rounded-[1.5rem] md:rounded-[2rem] bg-blue-400/30 blur-2xl animate-pulse" />
                                <span className="text-3xl md:text-5xl font-black text-white z-10 -rotate-3 transition-transform group-hover:scale-110">NX</span>
                            </motion.div>
                            <div className="space-y-4">
                                <h1 className="text-4xl md:text-6xl font-black tracking-tighter text-transparent bg-clip-text bg-gradient-to-b from-zinc-900 to-zinc-600 dark:from-white dark:to-zinc-500">
                                    Nexus Legal AI
                                </h1>
                                <p className="text-zinc-500 dark:text-zinc-400 max-w-sm leading-relaxed font-bold text-[10px] md:text-sm uppercase tracking-[0.1em]">
                                    Hệ thống Tư vấn Pháp luật Cao cấp <br className="hidden md:block" />
                                    <span className="text-blue-500 dark:text-blue-400 opacity-80 mt-2 block">Cơ sở dữ liệu VBLP Việt Nam</span>
                                </p>
                            </div>
                        </motion.div>
                    )}
                </AnimatePresence>

                <div ref={bottomRef} className="h-4 w-full shrink-0" />
            </div>
        </div>
    );
}
