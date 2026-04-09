"use client";

import * as React from "react";
import { ScrollArea } from "@/components/ui/scroll-area";
import { MessageItem } from "./message-item";
import { motion, AnimatePresence } from "framer-motion";

interface Message {
    id: string;
    role: "user" | "assistant";
    content: string;
    citations?: Array<{ id: number; source: string; page?: number }>;
    isStreaming?: boolean;
}

interface ChatAreaProps {
    messages: Message[];
}

export function ChatArea({ messages }: ChatAreaProps) {
    const scrollRef = React.useRef<HTMLDivElement>(null);

    // Auto-scroll to bottom
    React.useEffect(() => {
        if (scrollRef.current) {
            const scrollContainer = scrollRef.current.querySelector('[data-radix-scroll-area-viewport]');
            if (scrollContainer) {
                scrollContainer.scrollTop = scrollContainer.scrollHeight;
            }
        }
    }, [messages]);

    return (
        <ScrollArea ref={scrollRef} className="flex-1">
            <div className="flex flex-col min-h-full">
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
                        <div className="h-16 w-16 rounded-2xl bg-zinc-900 dark:bg-zinc-100 flex items-center justify-center shadow-xl">
                            <span className="text-2xl font-bold text-zinc-100 dark:text-zinc-900">A</span>
                        </div>
                        <h1 className="text-2xl font-bold tracking-tight text-zinc-900 dark:text-zinc-100">
                            Chào mừng đến với AI Document Chatbot
                        </h1>
                        <p className="text-zinc-500 dark:text-zinc-400 max-w-sm">
                            Tải lên tài liệu của bạn (PDF, Images) và nhận câu trả lời tức thì với trích dẫn chi tiết.
                        </p>
                    </div>
                )}

                <div className="h-40" /> {/* Spacer for bottom input */}
            </div>
        </ScrollArea>
    );
}
