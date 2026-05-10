"use client";

import * as React from "react";
import { Paperclip, Send, Square, X, FileText, Image as ImageIcon, Loader2, Search } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Progress } from "@/components/ui/progress";
import { motion, AnimatePresence } from "framer-motion";

interface ChatInputProps {
    onSend: (message: string, files: File[], retrieveOnly?: boolean) => void;
    onStop: () => void;
    isGenerating: boolean;
    forwardedInput?: string;
}

export function ChatInput({ onSend, onStop, isGenerating, forwardedInput }: ChatInputProps) {
    const [input, setInput] = React.useState("");
    const [files, setFiles] = React.useState<File[]>([]);
    const [isUploading, setIsUploading] = React.useState(false);
    const [uploadProgress, setUploadProgress] = React.useState(0);
    const [isRetrieveOnly, setIsRetrieveOnly] = React.useState(false);
    const textareaRef = React.useRef<HTMLTextAreaElement>(null);

    // Sync forwarded input
    React.useEffect(() => {
        if (forwardedInput) {
            setInput((prev) => (prev ? `${prev}\n> ${forwardedInput}` : `> ${forwardedInput}\n`));
            textareaRef.current?.focus();
        }
    }, [forwardedInput]);

    const handleSend = () => {
        if ((input.trim() || files.length > 0) && !isGenerating) {
            onSend(input, files, isRetrieveOnly);
            setInput("");
            setFiles([]);
        }
    };

    const handleDrop = (e: React.DragEvent) => {
        const text = e.dataTransfer.getData("text");
        if (text) {
            e.preventDefault();
            setInput((prev) => (prev ? `${prev}\n> ${text}` : `> ${text}\n`));
        }
    };

    const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        if (e.target.files) {
            const newFiles = Array.from(e.target.files);
            setFiles((prev) => [...prev, ...newFiles]);

            // Simulate upload/OCR process
            setIsUploading(true);
            setUploadProgress(10);
            let progress = 10;
            const interval = setInterval(() => {
                progress += 15;
                if (progress >= 100) {
                    setUploadProgress(100);
                    setIsUploading(false);
                    clearInterval(interval);
                } else {
                    setUploadProgress(progress);
                }
            }, 300);
        }
    };

    const removeFile = (index: number) => {
        setFiles((prev) => prev.filter((_, i) => i !== index));
    };

    // Auto-resize textarea
    React.useEffect(() => {
        if (textareaRef.current) {
            textareaRef.current.style.height = "inherit";
            const scrollHeight = textareaRef.current.scrollHeight;
            textareaRef.current.style.height = `${Math.min(scrollHeight, 200)}px`;
        }
    }, [input]);

    return (
        <div className="relative max-w-4xl mx-auto w-full px-4 md:px-8 pb-4 pt-2">
            <div
                onDragOver={(e) => e.preventDefault()}
                onDrop={handleDrop}
                className="relative rounded-2xl border border-zinc-200/50 dark:border-zinc-800/50 bg-zinc-900 shadow-2xl overflow-hidden focus-within:ring-1 focus-within:ring-zinc-600 transition-all backdrop-blur-xl"
            >

                {/* Upload Status / Files */}
                <AnimatePresence>
                    {files.length > 0 && (
                        <motion.div
                            initial={{ height: 0, opacity: 0 }}
                            animate={{ height: "auto", opacity: 1 }}
                            exit={{ height: 0, opacity: 0 }}
                            className="flex flex-wrap gap-2 p-3 bg-zinc-800/50 border-b border-zinc-700/50"
                        >
                            {files.map((file, i) => (
                                <div key={i} className="relative group flex items-center gap-2 p-2 rounded-lg bg-zinc-800 border border-zinc-700 text-xs text-zinc-200">
                                    {file.type.startsWith("image/") ? <ImageIcon className="h-3 w-3" /> : <FileText className="h-3 w-3" />}
                                    <span className="max-w-[100px] truncate">{file.name}</span>
                                    <button onClick={() => removeFile(i)} className="text-zinc-500 hover:text-red-400">
                                        <X className="h-3 w-3" />
                                    </button>
                                </div>
                            ))}
                        </motion.div>
                    )}
                </AnimatePresence>

                {isUploading && (
                    <div className="px-4 py-2 border-b border-zinc-700/50 bg-zinc-800/50">
                        <div className="flex items-center justify-between text-[10px] text-zinc-400 mb-1">
                            <span>Đang phân tích layout...</span>
                            <span>{uploadProgress}%</span>
                        </div>
                        <Progress value={uploadProgress} className="h-1 bg-zinc-700" />
                    </div>
                )}

                {/* Input Form */}
                <div className="flex flex-col p-2 sm:p-3">
                    <textarea
                        ref={textareaRef}
                        placeholder="Hỏi tài liệu..."
                        className="w-full min-h-[44px] max-h-[200px] bg-transparent border-none focus:ring-0 resize-none text-base text-zinc-100 placeholder:text-zinc-500 scrollbar-none px-2 py-2"
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onKeyDown={(e) => {
                            if (e.key === "Enter" && !e.shiftKey) {
                                e.preventDefault();
                                handleSend();
                            }
                        }}
                    />

                    {/* Action Bar Below Textarea */}
                    <div className="flex items-center justify-between mt-1 px-1">
                        <div className="flex items-center gap-1 sm:gap-2">
                            <input
                                type="file"
                                id="file-upload"
                                className="hidden"
                                multiple
                                onChange={handleFileChange}
                            />
                            <label htmlFor="file-upload">
                                <Button variant="ghost" size="icon" className="h-8 w-8 sm:h-9 sm:w-9 rounded-full text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800">
                                    <Paperclip className="h-4 w-4 sm:h-5 sm:w-5" />
                                </Button>
                            </label>

                            <Button
                                variant="ghost"
                                size="icon"
                                onClick={() => setIsRetrieveOnly(!isRetrieveOnly)}
                                className={cn(
                                    "h-8 w-8 sm:h-9 sm:w-9 rounded-full transition-colors",
                                    isRetrieveOnly ? "text-blue-400 bg-blue-900/30" : "text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800"
                                )}
                                title={isRetrieveOnly ? "Chế độ tìm trích dẫn (BGE Only)" : "Chế độ Chat (Full RAG)"}
                            >
                                <Search className="h-4 w-4 sm:h-5 sm:w-5" />
                            </Button>
                        </div>

                        <div>
                            {isGenerating ? (
                                <Button
                                    size="icon"
                                    onClick={onStop}
                                    className="h-8 w-8 sm:h-9 sm:w-9 rounded-xl bg-zinc-100 text-zinc-900 hover:bg-white"
                                >
                                    <Square className="h-3 w-3 sm:h-4 sm:w-4 fill-current" />
                                </Button>
                            ) : (
                                <Button
                                    size="icon"
                                    onClick={handleSend}
                                    disabled={!input.trim() && files.length === 0}
                                    className="h-8 w-8 sm:h-9 sm:w-9 rounded-xl bg-zinc-100 text-zinc-900 hover:bg-white disabled:bg-zinc-800 disabled:text-zinc-600"
                                >
                                    <Send className="h-3 w-3 sm:h-4 sm:w-4" />
                                </Button>
                            )}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}
