"use client";

import * as React from "react";
import { Paperclip, Send, Square, X, FileText, Image as ImageIcon, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Progress } from "@/components/ui/progress";
import { motion, AnimatePresence } from "framer-motion";

interface ChatInputProps {
    onSend: (message: string, files: File[]) => void;
    onStop: () => void;
    isGenerating: boolean;
    forwardedInput?: string;
}

export function ChatInput({ onSend, onStop, isGenerating, forwardedInput }: ChatInputProps) {
    const [input, setInput] = React.useState("");
    const [files, setFiles] = React.useState<File[]>([]);
    const [isUploading, setIsUploading] = React.useState(false);
    const [uploadProgress, setUploadProgress] = React.useState(0);
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
            onSend(input, files);
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
        <div className="relative max-w-4xl mx-auto w-full px-4 md:px-8 pb-8 pt-2">
            <div
                onDragOver={(e) => e.preventDefault()}
                onDrop={handleDrop}
                className="relative rounded-2xl border bg-white dark:bg-zinc-950 shadow-lg overflow-hidden focus-within:ring-1 focus-within:ring-zinc-400 dark:focus-within:ring-zinc-700 transition-all"
            >

                {/* Upload Status / Files */}
                <AnimatePresence>
                    {files.length > 0 && (
                        <motion.div
                            initial={{ height: 0, opacity: 0 }}
                            animate={{ height: "auto", opacity: 1 }}
                            exit={{ height: 0, opacity: 0 }}
                            className="flex flex-wrap gap-2 p-3 bg-zinc-50 dark:bg-zinc-900/50 border-b"
                        >
                            {files.map((file, i) => (
                                <div key={i} className="relative group flex items-center gap-2 p-2 rounded-lg bg-white dark:bg-zinc-800 border text-xs">
                                    {file.type.startsWith("image/") ? <ImageIcon className="h-3 w-3" /> : <FileText className="h-3 w-3" />}
                                    <span className="max-w-[100px] truncate">{file.name}</span>
                                    <button onClick={() => removeFile(i)} className="text-zinc-400 hover:text-red-500">
                                        <X className="h-3 w-3" />
                                    </button>
                                </div>
                            ))}
                        </motion.div>
                    )}
                </AnimatePresence>

                {isUploading && (
                    <div className="px-4 py-2 border-b bg-zinc-50 dark:bg-zinc-900/50">
                        <div className="flex items-center justify-between text-[10px] text-zinc-500 mb-1">
                            <span>Đang phân tích layout...</span>
                            <span>{uploadProgress}%</span>
                        </div>
                        <Progress value={uploadProgress} className="h-1" />
                    </div>
                )}

                {/* Input Form */}
                <div className="flex items-end gap-2 p-3">
                    <div className="flex-shrink-0 mb-1">
                        <input
                            type="file"
                            id="file-upload"
                            className="hidden"
                            multiple
                            onChange={handleFileChange}
                        />
                        <label htmlFor="file-upload">
                            <Button variant="ghost" size="icon" className="h-9 w-9 rounded-full text-zinc-500">
                                <Paperclip className="h-5 w-5" />
                            </Button>
                        </label>
                    </div>

                    <textarea
                        ref={textareaRef}
                        placeholder="Hỏi bất cứ điều gì về tài liệu của bạn..."
                        className="flex-1 min-h-[44px] max-h-[200px] py-3 bg-transparent border-none focus:ring-0 resize-none text-sm md:text-base scrollbar-none"
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onKeyDown={(e) => {
                            if (e.key === "Enter" && !e.shiftKey) {
                                e.preventDefault();
                                handleSend();
                            }
                        }}
                    />

                    <div className="flex-shrink-0 mb-1">
                        {isGenerating ? (
                            <Button
                                size="icon"
                                onClick={onStop}
                                className="h-9 w-9 rounded-xl bg-zinc-900 dark:bg-zinc-100 hover:bg-zinc-800 dark:hover:bg-zinc-200"
                            >
                                <Square className="h-4 w-4 fill-current" />
                            </Button>
                        ) : (
                            <Button
                                size="icon"
                                onClick={handleSend}
                                disabled={!input.trim() && files.length === 0}
                                className="h-9 w-9 rounded-xl bg-zinc-900 dark:bg-zinc-100 hover:bg-zinc-800 dark:hover:bg-zinc-200"
                            >
                                <Send className="h-4 w-4" />
                            </Button>
                        )}
                    </div>
                </div>
            </div>
            <p className="mt-3 text-[10px] text-zinc-400 text-center uppercase tracking-widest font-medium">
                AI Document Search & Chatbot v1.0
            </p>
        </div>
    );
}
