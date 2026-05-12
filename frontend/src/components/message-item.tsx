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
import { motion, AnimatePresence } from "framer-motion";

interface MessageItemProps {
    role: "user" | "assistant";
    content: string;
    citations?: Array<{ id: string | number; source: string; page?: number; content?: string; summary?: string; root_title?: string; hierarchy?: string }>;
    isStreaming?: boolean;
    isThinking?: boolean;
}

export function MessageItem({ role, content, citations, isStreaming, isThinking }: MessageItemProps) {
    const isAssistant = role === "assistant";
    const [selectedCite, setSelectedCite] = useState<any>(null);

    const cleanContent = content
        .replace(/\[STREAM_INIT\][\s\S]*?\n/g, "")
        .replace(/\[CITATIONS_JSON\][\s\S]*?(\[\/CITATIONS_JSON\]|$)/g, "")
        .replace(/\[STATUS\][\s\S]*?(\[\/STATUS\]|$)/g, "")
        .replace(/---/g, "")
        .replace(/### 🛡️ Nexus Legal AI - Tiến trình xử lý:\n/g, "")
        .replace(/<final_answer>|<\/final_answer>/g, "")
        .replace(/```json[\s\S]*?```/g, "")
        .replace(/\{[\s\n]*"citations":[\s\S]*\}\s*$/g, "") // Xóa khối JSON thô ở cuối
        .trim()
        .replace(/^[:\s\n,]+/, ""); // Xóa rác ở đầu câu

    const [showSources, setShowSources] = useState(false);

    const statusMatches = Array.from(content.matchAll(/\[STATUS\]([\s\S]*?)\[\/STATUS\]/g));
    const lastStatus = statusMatches.length > 0 ? statusMatches[statusMatches.length - 1][1] : null;

    const hasActualContent = cleanContent.length > 5; // Có ít nhất 5 ký tự câu trả lời thực tế
    const showStatus = isAssistant && lastStatus && isStreaming && !hasActualContent;

    return (
        <>
            <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.4, ease: "easeOut" }}
                className={cn(
                    "py-8 w-full border-b border-zinc-100/50 dark:border-zinc-900/50",
                    isAssistant ? "bg-zinc-50/10 dark:bg-zinc-950/20 backdrop-blur-sm" : "bg-transparent",
                    isThinking && "opacity-90"
                )}
            >
                <div className="max-w-4xl mx-auto flex gap-3 md:gap-6 px-4 md:px-6">
                    <div className={cn(
                        "h-9 w-9 rounded-xl flex items-center justify-center shrink-0 shadow-sm",
                        isAssistant ? "bg-zinc-900 text-zinc-100 dark:bg-zinc-100 dark:text-zinc-900" : "bg-blue-600 text-white"
                    )}>
                        {isAssistant ? <span className="text-xs md:text-sm font-bold">AI</span> : <span className="text-xs md:text-sm font-bold">U</span>}
                    </div>

                    <div className="flex-1 min-w-0 space-y-6">
                        <AnimatePresence mode="wait">
                            {showStatus && (
                                <motion.div
                                    key={lastStatus}
                                    initial={{ opacity: 0, scale: 0.95 }}
                                    animate={{ opacity: 1, scale: 1 }}
                                    exit={{ opacity: 0, scale: 1.05 }}
                                    transition={{ duration: 0.3 }}
                                    className="flex items-center gap-3 p-4 rounded-2xl border bg-white dark:bg-zinc-900 border-zinc-200 dark:border-zinc-800 shadow-xl shadow-blue-500/5 mb-6"
                                >
                                    <div className="h-6 w-6 rounded-lg bg-blue-600 flex items-center justify-center shrink-0 animate-pulse">
                                        <History className="h-3.5 w-3.5 text-white animate-spin-slow" />
                                    </div>
                                    <div className="flex-1">
                                        <p className="text-[10px] font-black text-blue-600 dark:text-blue-400 uppercase tracking-widest mb-1">Tiến trình xử lý</p>
                                        <p className="text-sm font-bold text-zinc-800 dark:text-zinc-200 tracking-tight">
                                            {lastStatus.includes("AI đang tra cứu") ? (
                                                <>
                                                    <span className="text-zinc-500 dark:text-zinc-400 font-medium mr-1">AI đang tra:</span>
                                                    <span className="text-blue-600 dark:text-blue-400 italic">
                                                        {lastStatus.split(":")[1]?.trim() || lastStatus}
                                                    </span>
                                                </>
                                            ) : (
                                                lastStatus.replace(/\*\*|🔍|📡|📚|⚖️|💡|🛡️/g, "").trim()
                                            )}
                                        </p>
                                    </div>
                                    <div className="flex gap-1">
                                        {[1, 2, 3].map(i => (
                                            <div key={i} className="h-1 w-1 rounded-full bg-blue-600 animate-bounce" style={{ animationDelay: `${i * 0.1}s` }} />
                                        ))}
                                    </div>
                                </motion.div>
                            )}
                        </AnimatePresence>

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
                                {cleanContent}
                            </ReactMarkdown>
                        </div>

                        {(() => {
                            let activeCitations = citations;
                            // Biên dịch JSON từ các tag chuyên dụng
                            if (isAssistant && (!activeCitations || activeCitations.length === 0)) {
                                try {
                                    const jsonMatch = content.match(/\[CITATIONS_JSON\]([\s\S]*?)\[\/CITATIONS_JSON\]/);
                                    if (jsonMatch && jsonMatch[1]) {
                                        const parsed = JSON.parse(jsonMatch[1].trim());
                                        activeCitations = Array.isArray(parsed) ? parsed : (parsed.citations || []);
                                    } else {
                                        // Fallback: Tìm kiếm khối JSON thô hoặc code block
                                        const rawJsonMatch = content.match(/```json\s*([\s\S]*?)```/) || content.match(/\[\s*\{"id":[\s\S]*\}\s*\]/);
                                        if (rawJsonMatch) {
                                            const rawData = JSON.parse(rawJsonMatch[1] || rawJsonMatch[0]);
                                            activeCitations = Array.isArray(rawData) ? rawData : (rawData.citations || []);
                                        }
                                    }
                                } catch (e) {
                                    console.error("Citation Parse Error:", e);
                                }
                            }

                            if (isAssistant && activeCitations && activeCitations.length > 0) {
                                return (
                                    <div className="space-y-4 pt-4 border-t border-zinc-200/50 dark:border-zinc-800/50">
                                        <button
                                            onClick={() => setShowSources(!showSources)}
                                            className="flex items-center gap-2 px-4 py-2 rounded-full bg-zinc-900 dark:bg-zinc-100 text-zinc-100 dark:text-zinc-900 text-xs font-bold hover:opacity-90 transition-all shadow-md group"
                                        >
                                            <History className="h-3.5 w-3.5 group-hover:rotate-12 transition-transform" />
                                            {showSources ? "Ẩn căn cứ pháp lý" : `Xem ${activeCitations.length} căn cứ pháp lý & Trích dẫn`}
                                            {showSources ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
                                        </button>

                                        {showSources && (
                                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-6 animate-in fade-in slide-in-from-top-2 duration-300">
                                                {activeCitations.map((cite: any, idx: number) => (
                                                    <CitationCard
                                                        key={cite.id || idx}
                                                        cite={cite}
                                                        onViewFull={() => setSelectedCite(cite)}
                                                    />
                                                ))}
                                            </div>
                                        )}
                                    </div>
                                );
                            }
                            return null;
                        })()}
                    </div>
                </div>
            </motion.div>

            <AnimatePresence>
                {selectedCite && (
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        className="fixed inset-0 z-[100] flex items-center justify-center p-4 md:p-8 bg-zinc-950/80 backdrop-blur-md"
                        onClick={() => setSelectedCite(null)}
                    >
                        <motion.div
                            initial={{ scale: 0.9, y: 20 }}
                            animate={{ scale: 1, y: 0 }}
                            exit={{ scale: 0.9, y: 20 }}
                            className="bg-white dark:bg-zinc-900 w-full max-w-4xl max-h-[85vh] rounded-3xl border border-zinc-200 dark:border-zinc-800 shadow-2xl flex flex-col overflow-hidden"
                            onClick={(e) => e.stopPropagation()}
                        >
                            <div className="p-6 border-b border-zinc-100 dark:border-zinc-800 flex items-center justify-between bg-zinc-50 dark:bg-zinc-900/50">
                                <div className="flex items-center gap-4">
                                    <div className="h-10 w-10 rounded-xl bg-blue-600 flex items-center justify-center shadow-lg overflow-hidden shrink-0">
                                        <span className="text-xs font-black text-white">
                                            {selectedCite.id?.toString().slice(-3)}
                                        </span>
                                    </div>
                                    <div>
                                        <h3 className="text-lg font-bold text-zinc-900 dark:text-white uppercase tracking-tight leading-none mb-1">
                                            {selectedCite.source}
                                        </h3>
                                        <p className="text-xs text-zinc-500 font-medium">Trích dẫn văn bản pháp luật gốc</p>
                                    </div>
                                </div>
                                <button
                                    onClick={() => setSelectedCite(null)}
                                    className="h-10 w-10 rounded-full hover:bg-zinc-200 dark:hover:bg-zinc-800 flex items-center justify-center transition-colors"
                                >
                                    <span className="text-2xl">&times;</span>
                                </button>
                            </div>

                            <div className="flex-1 overflow-y-auto p-8 custom-scrollbar">
                                <div className="max-w-3xl mx-auto space-y-6">
                                    <div className="p-4 rounded-2xl bg-blue-50 dark:bg-blue-900/10 border border-blue-100 dark:border-blue-800/30">
                                        <p className="text-[10px] font-black text-blue-600 dark:text-blue-400 uppercase tracking-widest mb-2">Cây phân cấp (Tree)</p>
                                        <p className="text-sm font-bold text-zinc-800 dark:text-zinc-200 italic leading-relaxed">
                                            {(() => {
                                                let h = selectedCite.hierarchy || selectedCite.source || "";
                                                if (h.length < 10 && selectedCite.content) {
                                                    const articleMatch = selectedCite.content.match(/(Điều \d+[\s\S]*?)(?:\n|$)/);
                                                    if (articleMatch) h = h ? `${h} > ${articleMatch[1].trim()}` : articleMatch[1].trim();
                                                }
                                                return h;
                                            })()}
                                        </p>
                                    </div>

                                    <div className="relative pt-4">
                                        <span className="absolute -left-4 -top-2 text-6xl text-zinc-200 dark:text-zinc-800 font-serif leading-none opacity-50">"</span>
                                        <div className="prose prose-zinc dark:prose-invert max-w-none">
                                            <p className="text-base md:text-lg leading-loose text-zinc-700 dark:text-zinc-300 font-serif whitespace-pre-wrap pl-2 italic">
                                                {(() => {
                                                    let c = selectedCite.content || "";
                                                    let h = selectedCite.hierarchy || selectedCite.source || "";
                                                    const articleMatch = c.match(/^(Điều \d+[\s\S]*?)(?:\n|$)/);
                                                    if (articleMatch) {
                                                        const articleTitle = articleMatch[1].trim();
                                                        if (h.includes(articleTitle) || (selectedCite.source && selectedCite.source.includes(articleTitle))) {
                                                            c = c.replace(articleMatch[0], "").trim();
                                                        }
                                                    }
                                                    return c;
                                                })()}
                                            </p>
                                        </div>
                                        <span className="absolute -right-2 bottom-0 text-6xl text-zinc-200 dark:text-zinc-800 font-serif leading-none opacity-50">"</span>
                                    </div>
                                </div>
                            </div>

                            <div className="p-6 border-t border-zinc-100 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900/50 flex flex-wrap justify-end gap-3">
                                <button
                                    onClick={() => {
                                        const searchQuery = `NGUỒN TRÍCH DẪN: [${selectedCite.full_hierarchy || selectedCite.hierarchy || selectedCite.source}]`;
                                        window.open(`https://www.google.com/search?q=${encodeURIComponent(searchQuery)}`, "_blank");
                                    }}
                                    className="px-6 py-2.5 rounded-xl bg-blue-600 text-white text-xs font-bold hover:bg-blue-500 transition-all flex items-center gap-2 shadow-lg shadow-blue-500/20"
                                >
                                    <ExternalLink className="h-3.5 w-3.5" />
                                    Tra cứu văn bản gốc
                                </button>
                                <button
                                    onClick={() => {
                                        navigator.clipboard.writeText(selectedCite.content);
                                    }}
                                    className="px-6 py-2.5 rounded-xl bg-zinc-900 dark:bg-white text-white dark:text-zinc-900 text-xs font-bold hover:opacity-90 transition-all flex items-center gap-2"
                                >
                                    <Copy className="h-3.5 w-3.5" />
                                    Sao chép nội dung
                                </button>
                                <button
                                    onClick={() => setSelectedCite(null)}
                                    className="px-6 py-2.5 rounded-xl bg-zinc-200 dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 text-xs font-bold hover:opacity-90 transition-all"
                                >
                                    Đóng
                                </button>
                            </div>
                        </motion.div>
                    </motion.div>
                )}
            </AnimatePresence>
        </>
    );
}

function CitationCard({ cite, onViewFull }: { cite: any, onViewFull: () => void }) {
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
        const searchQuery = `NGUỒN TRÍCH DẪN: [${cite.full_hierarchy || cite.hierarchy || cite.source}]`;
        window.open(`https://www.google.com/search?q=${encodeURIComponent(searchQuery)}`, "_blank");
    };

    // Logic thông minh để phục hồi Tree cho tin nhắn cũ và xóa trùng lặp
    const displayHierarchy = (() => {
        let h = cite.hierarchy || cite.source || "";
        // Nếu tree quá ngắn (chỉ có chữ LUẬT), thử tìm tiêu đề Điều trong content
        if (h.length < 10 && cite.content) {
            const articleMatch = cite.content.match(/(Điều \d+[\s\S]*?)(?:\n|$)/);
            if (articleMatch) h = h ? `${h} > ${articleMatch[1].trim()}` : articleMatch[1].trim();
        }
        return h;
    })();

    const displayContent = (() => {
        let c = cite.content || "";
        // Loại bỏ phần tiêu đề lặp lại ở đầu Content nếu nó đã có trong Tree/Source
        const articleMatch = c.match(/^(Điều \d+[\s\S]*?)(?:\n|$)/);
        if (articleMatch) {
            const articleTitle = articleMatch[1].trim();
            if (displayHierarchy.includes(articleTitle) || (cite.source && cite.source.includes(articleTitle))) {
                c = c.replace(articleMatch[0], "").trim();
            }
        }
        return c;
    })();

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
                        <div className="h-6 w-6 rounded-lg bg-blue-600 flex items-center justify-center shrink-0 shadow-sm overflow-hidden px-0.5">
                            <span className="text-[9px] font-black text-white truncate">
                                {cite.id?.toString().slice(-3)}
                            </span>
                        </div>
                        <h5 className="text-[11px] font-bold text-zinc-900 dark:text-zinc-100 truncate uppercase tracking-tight">
                            {cite.source}
                        </h5>
                    </div>
                </div>

                <div className="relative pl-3 border-l-2 border-blue-500/30">
                    <p className="text-[10px] font-bold text-zinc-500 dark:text-zinc-400 uppercase tracking-widest mb-1 flex items-center gap-1">
                        <History className="h-3 w-3" />
                        Cây phân cấp (Tree)
                    </p>
                    <p className="text-[11px] leading-relaxed text-zinc-800 dark:text-zinc-200 font-bold mb-3 italic line-clamp-4">
                        {displayHierarchy || "Đang truy xuất cây tiêu đề..."}
                    </p>

                    <p className="text-[10px] font-bold text-zinc-500 dark:text-zinc-400 uppercase tracking-widest mb-1">Tóm tắt kết luận</p>
                    <p className="text-[12px] leading-relaxed text-zinc-800 dark:text-zinc-200 font-medium line-clamp-2">
                        {cite.summary || "Dữ liệu tóm tắt đang được AI phân tích từ văn bản gốc..."}
                    </p>
                </div>
            </div>

            <div className={cn(
                "flex items-center border-t border-zinc-100 dark:border-zinc-800",
                expanded ? "bg-zinc-100 dark:bg-zinc-900" : "bg-zinc-50 dark:bg-zinc-900/50"
            )}>
                <button
                    onClick={() => setExpanded(!expanded)}
                    className="flex-1 flex items-center justify-between px-4 py-2.5 transition-colors text-left"
                >
                    <div className="flex items-center gap-2 text-[10px] font-bold text-blue-600 dark:text-blue-400 uppercase tracking-wider">
                        <History className="h-3.5 w-3.5" />
                        Trích dẫn nguyên văn
                    </div>
                    <div className="flex items-center gap-2">
                        {expanded ? <ChevronUp className="h-3.5 w-3.5 text-zinc-400" /> : <ChevronDown className="h-3.5 w-3.5 text-zinc-400" />}
                    </div>
                </button>

                <button
                    onClick={(e) => {
                        e.stopPropagation();
                        onViewFull();
                    }}
                    className="px-4 py-2.5 border-l border-zinc-200 dark:border-zinc-800 hover:bg-zinc-200 dark:hover:bg-zinc-800 transition-colors text-zinc-400 hover:text-blue-500"
                    title="Xem toàn màn hình"
                >
                    <ExternalLink className="h-3.5 w-3.5" />
                </button>
            </div>

            {expanded && (
                <div className="px-4 py-4 bg-zinc-50/50 dark:bg-zinc-900/20 border-t border-zinc-100 dark:border-zinc-800 animate-in fade-in slide-in-from-top-1 duration-300">
                    <div className="relative">
                        <span className="absolute -left-2 -top-1 text-3xl text-zinc-200 dark:text-zinc-800 font-serif leading-none">"</span>
                        <p className="text-[11.5px] leading-relaxed text-zinc-600 dark:text-zinc-400 whitespace-pre-wrap font-serif pl-2 italic line-clamp-[8]">
                            {displayContent || "Nội dung trích dẫn đang được tải từ dữ liệu gốc..."}
                        </p>
                        <span className="absolute -right-1 -bottom-2 text-3xl text-zinc-200 dark:text-zinc-800 font-serif leading-none">"</span>
                    </div>

                    <div className="mt-4 pt-3 border-t border-zinc-200/30 dark:border-zinc-800/30 flex justify-between items-center">
                        <button
                            onClick={openSource}
                            className="text-[9px] flex items-center gap-1.5 text-zinc-400 hover:text-blue-500 transition-colors font-bold uppercase tracking-tighter group"
                        >
                            Tra cứu văn bản gốc
                            <ExternalLink className="h-3 w-3 group-hover:translate-x-0.5 group-hover:-translate-y-0.5 transition-transform" />
                        </button>
                        <div className="flex items-center gap-2">
                            <div
                                onClick={copyText}
                                className="p-1 hover:bg-zinc-200 dark:hover:bg-zinc-800 rounded transition-colors cursor-pointer"
                            >
                                {copied ? <Check className="h-3 w-3 text-green-500" /> : <Copy className="h-3 w-3 text-zinc-400" />}
                            </div>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
