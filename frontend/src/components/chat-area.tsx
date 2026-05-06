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
            className="flex-1 w-full overflow-y-auto"
        >
            <div className="max-w-4xl mx-auto flex flex-col min-h-full pb-32 px-4">
                <AnimatePresence initial={false}>
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
                            />
                        </motion.div>
                    ))}
                </AnimatePresence>

                {/* Welcome screen when empty */}
                {messages.length === 0 && (
                    <div className="flex-1 flex flex-col items-center justify-center p-8 text-center space-y-8 pt-32">
                        <motion.div 
                            initial={{ scale: 0.8, opacity: 0 }}
                            animate={{ scale: 1, opacity: 1 }}
                            transition={{ duration: 0.5, type: "spring" }}
                            className="h-24 w-24 rounded-3xl bg-gradient-to-br from-blue-600 via-indigo-600 to-purple-600 flex items-center justify-center shadow-2xl rotate-6 relative"
                        >
                            <div className="absolute inset-0 rounded-3xl bg-blue-400/20 blur-xl animate-pulse" />
                            <span className="text-4xl font-black text-white z-10">NX</span>
                        </motion.div>
                        <div className="space-y-4">
                            <h1 className="text-5xl font-black tracking-tighter text-transparent bg-clip-text bg-gradient-to-r from-zinc-900 to-zinc-500 dark:from-white dark:to-zinc-500">
                                Nexus Legal AI
                            </h1>
                            <p className="text-zinc-500 dark:text-zinc-400 max-w-md leading-relaxed font-medium">
                                Hệ thống Tư vấn Pháp luật Cao cấp sử dụng công nghệ RAG V15. <br/> 
                                <span className="text-blue-500 dark:text-blue-400">Trích xuất chính xác - Phân tích chuyên sâu - Tư vấn tận tâm.</span>
                            </p>
                        </div>
                    </div>
                )}

                <div ref={bottomRef} className="h-4 w-full shrink-0" />
            </div>
        </div>
    );
}
