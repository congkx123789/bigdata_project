"use client";

import * as React from "react";
import { 
    Plus, 
    History, 
    User, 
    LogOut, 
    ChevronLeft, 
    ChevronRight, 
    MessageSquare, 
    MoreVertical,
    Settings as SettingsIcon 
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { motion, AnimatePresence } from "framer-motion";
import { api, ChatHistoryGroup } from "@/lib/api";

interface SidebarProps {
    className?: string;
    onOpenSettings?: () => void;
    onNewChat?: () => void;
    onSelectSession?: (sessionId: string) => void;
    isOpen?: boolean;
    setIsOpen?: (open: boolean) => void;
    userId: string;
    currentSessionId: string;
}

export function Sidebar({ className, onOpenSettings, onNewChat, onSelectSession, isOpen, setIsOpen, userId, currentSessionId }: SidebarProps) {
    const [isDesktopCollapsed, setIsDesktopCollapsed] = React.useState(false);
    const [sessions, setSessions] = React.useState<any[]>([]);
    const [isLoading, setIsLoading] = React.useState(true);

    React.useEffect(() => {
        if (userId === "anonymous") return;
        async function fetchHistory() {
            try {
                const data = await api.getSessionList(userId);
                setSessions(data || []);
            } catch (err) {
                console.error("Failed to fetch history:", err);
            } finally {
                setIsLoading(false);
            }
        }
        fetchHistory();
    }, [userId, currentSessionId]);

    return (
        <motion.div
            initial={false}
            animate={{ width: isDesktopCollapsed ? 80 : 300 }}
            className={cn(
                "fixed md:relative inset-y-0 left-0 z-50 flex flex-col h-[100dvh] bg-zinc-950 border-r border-white/5 transition-all duration-300",
                isOpen ? "translate-x-0 shadow-2xl" : "-translate-x-full md:translate-x-0",
                className
            )}
        >
            {/* Sidebar Header */}
            <div className="p-6 flex items-center justify-between">
                {!isDesktopCollapsed && (
                    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex items-center gap-3">
                        <div className="h-8 w-8 rounded-lg bg-gradient-to-br from-blue-600 to-indigo-600 flex items-center justify-center shadow-lg shadow-blue-500/20">
                            <span className="text-white font-black text-sm">NX</span>
                        </div>
                        <span className="font-bold text-lg tracking-tighter text-zinc-100 uppercase">Nexus AI</span>
                    </motion.div>
                )}
                {isDesktopCollapsed && (
                    <div className="h-8 w-8 rounded-lg bg-blue-600 flex items-center justify-center mx-auto">
                        <span className="text-white font-black text-xs">NX</span>
                    </div>
                )}
                <Button 
                    variant="ghost" 
                    size="icon" 
                    onClick={() => setIsOpen?.(false)} 
                    className="md:hidden h-9 w-9 text-zinc-500 hover:text-zinc-100 hover:bg-zinc-900"
                >
                    <ChevronLeft className="h-6 w-6" />
                </Button>
            </div>

            {/* New Chat Button */}
            <div className="px-4 pb-4">
                <Button
                    onClick={() => {
                        onNewChat?.();
                        setIsOpen?.(false);
                    }}
                    className={cn(
                        "w-full justify-start gap-3 bg-zinc-100 text-zinc-950 hover:bg-white transition-all rounded-2xl h-12 shadow-lg group",
                        isDesktopCollapsed && "px-0 justify-center"
                    )}
                >
                    <Plus className="h-5 w-5 shrink-0 group-hover:rotate-90 transition-transform duration-300" />
                    {!isDesktopCollapsed && <span className="font-bold text-sm uppercase tracking-tight">Tư vấn mới</span>}
                </Button>
            </div>

            {/* Session List */}
            <ScrollArea className="flex-1 px-4 py-2">
                {!isDesktopCollapsed && (
                    <div className="space-y-6">
                        <div className="space-y-1">
                            <h3 className="text-[10px] font-black text-zinc-500 uppercase tracking-[0.2em] mb-4 px-2">
                                Lịch sử hội thoại
                            </h3>
                            <div className="space-y-1">
                                {sessions.length > 0 ? (
                                    sessions.map((session) => (
                                        <button
                                            key={session.session_id}
                                            onClick={() => {
                                                onSelectSession?.(session.session_id);
                                                setIsOpen?.(false);
                                            }}
                                            className={cn(
                                                "w-full text-left px-4 py-3 text-sm rounded-xl transition-all flex items-center gap-3 group relative border",
                                                currentSessionId === session.session_id 
                                                    ? "bg-zinc-900 border-zinc-800 text-zinc-100 shadow-sm" 
                                                    : "bg-transparent border-transparent text-zinc-500 hover:bg-zinc-900/50 hover:text-zinc-300"
                                            )}
                                        >
                                            <MessageSquare className={cn(
                                                "h-4 w-4 shrink-0 transition-colors",
                                                currentSessionId === session.session_id ? "text-blue-500" : "text-zinc-600 group-hover:text-zinc-400"
                                            )} />
                                            <span className="truncate flex-1 font-medium">{session.title}</span>
                                            
                                            <Button 
                                                variant="ghost" 
                                                size="icon" 
                                                className="h-7 w-7 opacity-0 group-hover:opacity-100 transition-opacity rounded-lg"
                                                onClick={(e) => {
                                                    e.stopPropagation();
                                                }}
                                            >
                                                <MoreVertical className="h-4 w-4" />
                                            </Button>
                                        </button>
                                    ))
                                ) : isLoading ? (
                                    <div className="space-y-3 px-2">
                                        {[1, 2, 3].map((i) => (
                                            <div key={i} className="h-10 w-full bg-zinc-900 animate-pulse rounded-xl" />
                                        ))}
                                    </div>
                                ) : (
                                    <p className="text-xs text-zinc-600 px-4 py-8 text-center italic">Chưa có lịch sử</p>
                                )}
                            </div>
                        </div>
                    </div>
                )}
                {isDesktopCollapsed && (
                    <div className="flex flex-col items-center gap-6 py-4">
                        <History className="h-5 w-5 text-zinc-500 hover:text-zinc-300 transition-colors cursor-pointer" />
                    </div>
                )}
            </ScrollArea>

            {/* Sidebar Footer */}
            <div className="p-4 mt-auto">
                <div className={cn(
                    "bg-zinc-900/50 border border-zinc-800 p-3 rounded-2xl flex items-center gap-3",
                    isDesktopCollapsed && "flex-col p-2"
                )}>
                    <Avatar className="h-9 w-9 border border-zinc-700">
                        <AvatarFallback className="bg-zinc-800 text-zinc-400">
                            <User className="h-5 w-5" />
                        </AvatarFallback>
                    </Avatar>

                    {!isDesktopCollapsed && (
                        <div className="flex-1 min-w-0">
                            <p className="text-[11px] font-black text-zinc-500 uppercase tracking-widest">Người dùng</p>
                            <p className="text-sm font-bold text-zinc-100 truncate">Khách hàng ẩn danh</p>
                        </div>
                    )}

                    <div className={cn("flex items-center", isDesktopCollapsed ? "flex flex-col gap-1" : "gap-1")}>
                        <Button 
                            variant="ghost" 
                            size="icon" 
                            onClick={onOpenSettings}
                            className="h-8 w-8 text-zinc-500 hover:text-zinc-100 hover:bg-zinc-800 rounded-lg"
                        >
                            <SettingsIcon className="h-4 w-4" />
                        </Button>
                    </div>
                </div>
            </div>

            {/* Desktop Toggle */}
            <button
                onClick={() => setIsDesktopCollapsed(!isDesktopCollapsed)}
                className="hidden md:flex absolute -right-3 top-1/2 -translate-y-1/2 h-6 w-6 rounded-full border border-zinc-800 bg-zinc-950 text-zinc-500 items-center justify-center hover:bg-zinc-900 hover:text-zinc-100 transition-all shadow-xl z-10"
            >
                {isDesktopCollapsed ? <ChevronRight className="h-3 w-3" /> : <ChevronLeft className="h-3 w-3" />}
            </button>
        </motion.div>
    );
}
