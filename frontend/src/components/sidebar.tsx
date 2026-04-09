"use client";

import * as React from "react";
import { Plus, History, User, LogOut, ChevronLeft, ChevronRight, MessageSquare } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Separator } from "@/components/ui/separator";
import { motion, AnimatePresence } from "framer-motion";
import { api, ChatHistoryGroup } from "@/lib/api";


interface SidebarProps {
    className?: string;
}

export function Sidebar({ className }: SidebarProps) {
    const [isCollapsed, setIsCollapsed] = React.useState(false);

    // Real data from API
    const [historyGroups, setHistoryGroups] = React.useState<ChatHistoryGroup[]>([]);
    const [isLoading, setIsLoading] = React.useState(true);

    React.useEffect(() => {
        async function fetchHistory() {
            try {
                const data = await api.getChatHistory();
                if (data && data.length > 0) {
                    setHistoryGroups(data);
                }
            } catch (err) {
                console.error("Failed to fetch history:", err);
            } finally {
                setIsLoading(false);
            }
        }
        fetchHistory();
    }, []);

    return (
        <motion.div
            initial={false}
            animate={{ width: isCollapsed ? 80 : 280 }}
            className={cn(
                "relative flex flex-col h-screen border-r bg-zinc-50 dark:bg-zinc-950 transition-colors duration-300",
                className
            )}
        >
            {/* Header - New Conversation */}
            <div className="p-4">
                <Button
                    className={cn(
                        "w-full justify-start gap-2 bg-zinc-900 text-zinc-50 hover:bg-zinc-800 dark:bg-zinc-50 dark:text-zinc-950 dark:hover:bg-zinc-200 transition-all",
                        isCollapsed && "px-2 justify-center"
                    )}
                    size={isCollapsed ? "icon" : "default"}
                >
                    <Plus className="h-5 w-5 shrink-0" />
                    {!isCollapsed && <span className="font-medium truncate">New Conversation</span>}
                </Button>
            </div>

            <ScrollArea className="flex-1 px-4">
                <AnimatePresence>
                    {!isCollapsed && (
                        <motion.div
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            exit={{ opacity: 0 }}
                            transition={{ duration: 0.2 }}
                        >
                            {historyGroups.length > 0 ? (
                                historyGroups.map((group) => (
                                    <div key={group.label} className="mb-6">
                                        <h3 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-2 px-2">
                                            {group.label}
                                        </h3>
                                        <div className="space-y-1">
                                            {group.chats.map((chat) => (
                                                <button
                                                    key={chat.id}
                                                    className="w-full text-left px-2 py-2 text-sm rounded-md hover:bg-zinc-200 dark:hover:bg-zinc-900 transition-colors flex items-center gap-2 group"
                                                >
                                                    <MessageSquare className="h-4 w-4 shrink-0 text-zinc-400 group-hover:text-zinc-600 dark:group-hover:text-zinc-300" />
                                                    <span className="truncate text-zinc-700 dark:text-zinc-300">{chat.title}</span>
                                                </button>
                                            ))}
                                        </div>
                                    </div>
                                ))
                            ) : isLoading ? (
                                <div className="space-y-4 py-4">
                                    {[1, 2, 3].map((i) => (
                                        <div key={i} className="h-8 w-full bg-zinc-200 dark:bg-zinc-800 animate-pulse rounded-md" />
                                    ))}
                                </div>
                            ) : (
                                <p className="text-xs text-zinc-500 px-2">Chưa có lịch sử trò chuyện</p>
                            )}
                        </motion.div>
                    )}
                </AnimatePresence>

                {isCollapsed && (
                    <div className="flex flex-col items-center gap-4 py-4">
                        <History className="h-5 w-5 text-zinc-500" />
                    </div>
                )}
            </ScrollArea>

            {/* Footer - User Profile */}
            <div className="p-4 border-t bg-zinc-50/50 dark:bg-zinc-950/50 backdrop-blur-sm">
                <div className={cn(
                    "flex items-center gap-3",
                    isCollapsed && "flex-col"
                )}>
                    <Avatar className="h-9 w-9 border border-zinc-200 dark:border-zinc-800">
                        <AvatarImage src="/avatar-placeholder.png" />
                        <AvatarFallback><User className="h-5 w-5" /></AvatarFallback>
                    </Avatar>

                    {!isCollapsed && (
                        <div className="flex-1 min-w-0">
                            <p className="text-sm font-medium truncate dark:text-zinc-100">Expert Developer</p>
                            <p className="text-xs text-zinc-500 truncate">user@example.com</p>
                        </div>
                    )}

                    <Button variant="ghost" size="icon" className={cn(
                        "h-8 w-8 text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100",
                        isCollapsed ? "mt-2" : "ml-auto"
                    )}>
                        <LogOut className="h-4 w-4" />
                    </Button>
                </div>
            </div>

            {/* Toggle Button */}
            <button
                onClick={() => setIsCollapsed(!isCollapsed)}
                className="absolute -right-3 top-1/2 -translate-y-1/2 h-6 w-6 rounded-full border bg-background flex items-center justify-center hover:bg-accent transition-colors shadow-sm z-10"
            >
                {isCollapsed ? <ChevronRight className="h-3 w-3" /> : <ChevronLeft className="h-3 w-3" />}
            </button>
        </motion.div>
    );
}
