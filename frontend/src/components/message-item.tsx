"use client";

import React, { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism";
import "katex/dist/katex.min.css";
import { Check, Copy, ChevronDown, ChevronUp, FileText, ExternalLink, History } from "lucide-react";
import { cn } from "@/lib/utils";

interface MessageItemProps {
    role: "user" | "assistant";
    content: string;
    citations?: Array<{ id: number; source: string; page?: number; content?: string; summary?: string }>;
    isStreaming?: boolean;
}

export function MessageItem({ role, content, citations, isStreaming }: MessageItemProps) {
    const isAssistant = role === "assistant";
    const [showSources, setShowSources] = useState(false);

    return (
        <div className={cn(
            "py-8 w-full border-b border-zinc-100/50 dark:border-zinc-900/50",
            isAssistant ? "bg-zinc-50/30 dark:bg-zinc-950/30" : "bg-transparent"
        )}>
            <div className="max-w-4xl mx-auto flex gap-6 px-4 md:px-6">
                <div className={cn(
                    "h-9 w-9 rounded-xl flex items-center justify-center shrink-0 shadow-sm",
                    isAssistant ? "bg-zinc-900 text-zinc-100 dark:bg-zinc-100 dark:text-zinc-900" : "bg-blue-600 text-white"
                )}>
                    {isAssistant ? <span className="text-sm font-bold">AI</span> : <span className="text-sm font-bold">U</span>}
                </div>

                <div className="flex-1 min-w-0 space-y-6">
                    <div className="prose prose-zinc dark:prose-invert max-w-none prose-p:leading-relaxed prose-p:text-zinc-800 dark:prose-p:text-zinc-200 prose-headings:font-bold">
                        <ReactMarkdown
                            remarkPlugins={[remarkMath]}
                            rehypePlugins={[rehypeKatex]}
                            components={{
                                code({ node, inline, className, children, ...props }: any) {
                                    const match = /language-(\w+)/.exec(className || "");
                                    return !inline && match ? (
                                        <SyntaxHighlighter
                                            style={oneDark}
                                            language={match[1]}
                                            PreTag="div"
                                            {...props}
                                        >
                                            {String(children).replace(/\n$/, "")}
                                        </SyntaxHighlighter>
                                    ) : (
                                        <code className={cn("bg-zinc-200 dark:bg-zinc-800 px-1 py-0.5 rounded text-sm", className)} {...props}>
                                            {children}
                                        </code>
                                    );
                                },
                            }}
                        >
                            {content}
                        </ReactMarkdown>
                    </div>

                    {isAssistant && isStreaming && (
                        <div className="flex gap-1.5 items-center pt-2">
                            <div className="h-1.5 w-1.5 rounded-full bg-zinc-400 animate-bounce" style={{ animationDelay: "0ms" }} />
                            <div className="h-1.5 w-1.5 rounded-full bg-zinc-400 animate-bounce" style={{ animationDelay: "150ms" }} />
                            <div className="h-1.5 w-1.5 rounded-full bg-zinc-400 animate-bounce" style={{ animationDelay: "300ms" }} />
                        </div>
                    )}

                    {isAssistant && !isStreaming && citations && citations.length > 0 && (
                        <div className="space-y-4 pt-4 border-t border-zinc-200/50 dark:border-zinc-800/50">
                            <button
                                onClick={() => setShowSources(!showSources)}
                                className="flex items-center gap-2 px-4 py-2 rounded-full bg-zinc-900 dark:bg-zinc-100 text-zinc-100 dark:text-zinc-900 text-xs font-bold hover:opacity-90 transition-all shadow-md group"
                            >
                                <History className="h-3.5 w-3.5 group-hover:rotate-12 transition-transform" />
                                {showSources ? "Ẩn căn cứ pháp lý" : `Xem ${citations.length} căn cứ pháp lý & Trích dẫn`}
                                {showSources ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
                            </button>

                            {showSources && (
                                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-6 animate-in fade-in slide-in-from-top-2 duration-300">
                                    {citations.map((cite) => (
                                        <CitationCard key={cite.id} cite={cite} />
                                    ))}
                                </div>
                            )}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}

function CitationCard({ cite }: { cite: any }) {
    const [expanded, setExpanded] = useState(false);
    const [copied, setCopied] = useState(false);

    const copyText = (e: React.MouseEvent) => {
        e.stopPropagation();
        if (cite.content) {
            navigator.clipboard.writeText(cite.content);
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
        }
    };

    const openSource = (e: React.MouseEvent) => {
        e.stopPropagation();
        window.open(`https://www.google.com/search?q=${encodeURIComponent(cite.source + " luật Việt Nam")}`, "_blank");
    };

    return (
        <div 
            className={cn(
                "group flex flex-col rounded-2xl border transition-all duration-300 overflow-hidden shadow-sm hover:shadow-md",
                expanded 
                    ? "bg-white dark:bg-zinc-900 border-blue-500/50 scale-[1.02] z-10" 
                    : "bg-white/50 dark:bg-zinc-900/50 border-zinc-200 dark:border-zinc-800 hover:border-zinc-300 dark:hover:border-zinc-700"
            )}
        >
            <div className="p-4 space-y-3">
                <div className="flex items-center justify-between gap-3">
                    <div className="flex items-center gap-2 min-w-0">
                        <div className="h-6 w-6 rounded-lg bg-zinc-100 dark:bg-zinc-800 flex items-center justify-center shrink-0">
                            <FileText className="h-3.5 w-3.5 text-zinc-500" />
                        </div>
                        <h5 className="text-[11px] font-bold text-zinc-900 dark:text-zinc-100 truncate uppercase tracking-tight">
                            {cite.source}
                        </h5>
                    </div>
                    {cite.page && (
                        <span className="text-[10px] bg-zinc-100 dark:bg-zinc-800 px-1.5 py-0.5 rounded text-zinc-500 font-medium shrink-0">
                            Trang {cite.page}
                        </span>
                    )}
                </div>

                <div className="relative pl-3 border-l-2 border-blue-500/30">
                    <p className="text-[12px] leading-relaxed text-zinc-800 dark:text-zinc-200 font-medium italic line-clamp-3">
                        {cite.summary || "Bản tóm tắt kết luận pháp lý đang được cập nhật..."}
                    </p>
                </div>
            </div>

            <button
                onClick={() => setExpanded(!expanded)}
                className={cn(
                    "flex items-center justify-between px-4 py-2.5 transition-colors text-left border-t border-zinc-100 dark:border-zinc-800",
                    expanded ? "bg-zinc-100 dark:bg-zinc-900" : "bg-zinc-50 dark:bg-zinc-900/50 hover:bg-zinc-100 dark:hover:bg-zinc-900"
                )}
            >
                <div className="flex items-center gap-2 text-[10px] font-bold text-blue-600 dark:text-blue-400 uppercase tracking-wider">
                    <History className="h-3.5 w-3.5" />
                    Trích dẫn nguyên văn
                </div>
                <div className="flex items-center gap-2">
                    {expanded && (
                        <div 
                            onClick={copyText}
                            className="p-1 hover:bg-zinc-200 dark:hover:bg-zinc-800 rounded transition-colors"
                        >
                            {copied ? <Check className="h-3 w-3 text-green-500" /> : <Copy className="h-3 w-3 text-zinc-400" />}
                        </div>
                    )}
                    {expanded ? <ChevronUp className="h-3.5 w-3.5 text-zinc-400" /> : <ChevronDown className="h-3.5 w-3.5 text-zinc-400" />}
                </div>
            </button>

            {expanded && (
                <div className="px-4 py-4 bg-zinc-50/50 dark:bg-zinc-900/20 border-t border-zinc-100 dark:border-zinc-800 animate-in fade-in slide-in-from-top-1 duration-300">
                    <div className="relative">
                        <span className="absolute -left-2 -top-1 text-3xl text-zinc-200 dark:text-zinc-800 font-serif leading-none">"</span>
                        <p className="text-[11.5px] leading-relaxed text-zinc-600 dark:text-zinc-400 whitespace-pre-wrap font-serif pl-2 italic">
                            {cite.content}
                        </p>
                        <span className="absolute -right-1 -bottom-2 text-3xl text-zinc-200 dark:text-zinc-800 font-serif leading-none">"</span>
                    </div>
                    
                    <div className="mt-4 pt-3 border-t border-zinc-200/30 dark:border-zinc-800/30 flex justify-between items-center">
                        <div className="flex items-center gap-1.5">
                            <div className="h-1.5 w-1.5 rounded-full bg-green-500 animate-pulse"></div>
                            <span className="text-[9px] text-zinc-400 font-medium uppercase tracking-widest">Nguồn xác thực</span>
                        </div>
                        <button 
                            onClick={openSource}
                            className="text-[9px] flex items-center gap-1.5 text-zinc-400 hover:text-blue-500 transition-colors font-bold uppercase tracking-tighter group"
                        >
                            Tra cứu văn bản gốc 
                            <ExternalLink className="h-3 w-3 group-hover:translate-x-0.5 group-hover:-translate-y-0.5 transition-transform" />
                        </button>
                    </div>
                </div>
            )}
        </div>
    );
}
