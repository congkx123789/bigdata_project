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
            bottomRef.current.scrollIntoView({ behavior: "smooth" });
        }
    }, [messages]);

    return (
        <div 
            ref={scrollRef} 
            className="flex-1 w-full overflow-y-auto"
            style={{ height: 'calc(100vh - 180px)' }}
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
                    <div className="flex-1 flex flex-col items-center justify-center p-8 text-center space-y-4 pt-20">
                        <div className="h-20 w-20 rounded-3xl bg-zinc-950 dark:bg-zinc-50 flex items-center justify-center shadow-2xl rotate-3">
                            <span className="text-3xl font-bold text-zinc-50 dark:text-zinc-950">AI</span>
                        </div>
                        <h1 className="text-3xl font-bold tracking-tight text-zinc-900 dark:text-zinc-100">
                            Pháp Điển AI - Trợ Lý Pháp Lý
                        </h1>
                        <p className="text-zinc-500 dark:text-zinc-400 max-w-sm leading-relaxed">
                            Tra cứu văn bản pháp luật, trích xuất căn cứ chính xác và phân tích chuyên sâu với công nghệ RAG.
                        </p>
                    </div>
                )}

                <div ref={bottomRef} className="h-4 w-full shrink-0" />
            </div>
        </div>
    );
}
