"use client";

import ReactMarkdown from "react-markdown";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism";
import "katex/dist/katex.min.css";
import { Check, Copy } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useState } from "react";
import { cn } from "@/lib/utils";

interface MessageItemProps {
    role: "user" | "assistant";
    content: string;
    citations?: Array<{ id: number; source: string; page?: number }>;
    isStreaming?: boolean;
}

export function MessageItem({ role, content, citations, isStreaming }: MessageItemProps) {
    const [copied, setCopied] = useState(false);

    const copyToClipboard = (text: string) => {
        navigator.clipboard.writeText(text);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };

    return (
        <div
            className={cn(
                "flex w-full gap-4 py-8 px-4 md:px-8 first:pt-4",
                role === "assistant" ? "bg-zinc-100/50 dark:bg-zinc-900/40" : "bg-transparent"
            )}
        >
            <div className="flex-1 max-w-4xl mx-auto flex gap-4 md:gap-6">
                {/* Avatar/Icon */}
                <div className="flex-shrink-0 mt-1">
                    {role === "assistant" ? (
                        <div className="h-8 w-8 rounded-lg bg-zinc-900 dark:bg-zinc-100 flex items-center justify-center shadow-sm">
                            <span className="text-[10px] font-bold text-zinc-100 dark:text-zinc-900">AI</span>
                        </div>
                    ) : (
                        <div className="h-8 w-8 rounded-lg bg-zinc-200 dark:bg-zinc-800 flex items-center justify-center">
                            <span className="text-[10px] font-bold text-zinc-600 dark:text-zinc-400">ME</span>
                        </div>
                    )}
                </div>

                {/* Content Area */}
                <div className="flex-1 min-w-0 space-y-4">
                    <div className="prose dark:prose-invert max-w-none break-words">
                        <ReactMarkdown
                            remarkPlugins={[remarkMath]}
                            rehypePlugins={[rehypeKatex]}
                            components={{
                                code({ node, inline, className, children, ...props }: any) {
                                    const match = /language-(\w+)/.exec(className || "");
                                    return !inline && match ? (
                                        <div className="relative group rounded-md overflow-hidden my-4 border border-zinc-200 dark:border-zinc-800">
                                            <div className="flex items-center justify-between px-4 py-2 bg-zinc-200/50 dark:bg-zinc-800/50 text-xs text-zinc-500 font-mono">
                                                <span>{match[1]}</span>
                                                <button
                                                    onClick={() => copyToClipboard(String(children).replace(/\n$/, ""))}
                                                    className="hover:text-zinc-900 dark:hover:text-zinc-100 transition-colors"
                                                >
                                                    {copied ? <Check className="h-3 w-3" /> : <Copy className="h-3 w-3" />}
                                                </button>
                                            </div>
                                            <SyntaxHighlighter
                                                style={oneDark}
                                                language={match[1]}
                                                PreTag="div"
                                                className="!m-0 !bg-zinc-950/90"
                                                {...props}
                                            >
                                                {String(children).replace(/\n$/, "")}
                                            </SyntaxHighlighter>
                                        </div>
                                    ) : (
                                        <code className={cn("bg-zinc-200 dark:bg-zinc-800 px-1 py-0.5 rounded text-sm", className)} {...props}>
                                            {children}
                                        </code>
                                    );
                                },
                            }}
                        >
                            {content + (isStreaming ? " ▍" : "")}
                        </ReactMarkdown>
                    </div>

                    {/* Citations */}
                    {citations && citations.length > 0 && (
                        <div className="flex flex-wrap gap-2 pt-2">
                            {citations.map((cite) => (
                                <div key={cite.id} className="group relative">
                                    <span className="inline-flex items-center justify-center h-5 w-5 rounded bg-zinc-200 dark:bg-zinc-800 text-[10px] font-bold text-zinc-600 dark:text-zinc-400 cursor-help hover:bg-zinc-300 dark:hover:bg-zinc-700 transition-colors">
                                        {cite.id}
                                    </span>

                                    {/* Tooltip detail */}
                                    <div className="absolute bottom-full left-0 mb-2 w-64 p-3 bg-white dark:bg-zinc-950 border rounded-lg shadow-xl opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all z-50 transform translate-y-2 group-hover:translate-y-0">
                                        <p className="text-xs font-semibold text-zinc-900 dark:text-zinc-100 truncate">{cite.source}</p>
                                        {cite.page && <p className="text-[10px] text-zinc-500 mt-1">Trang {cite.page}</p>}
                                        <div className="mt-2 text-[10px] text-blue-500 hover:underline cursor-pointer">Xem tài liệu gốc</div>
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
