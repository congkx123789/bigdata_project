"use client";

import * as React from "react";
import { Sidebar } from "@/components/sidebar";
import { ChatArea } from "@/components/chat-area";
import { ChatInput } from "@/components/chat-input";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations?: Array<{ id: number; source: string; page?: number; content?: string }>;
  isStreaming?: boolean;
}

import { AppSettings, SettingsDialog } from "@/components/settings-dialog";
import { Menu } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function Home() {
  const [messages, setMessages] = React.useState<Message[]>([]);
  const [isGenerating, setIsGenerating] = React.useState(false);
  const [forwardedInput, setForwardedInput] = React.useState<string | undefined>(undefined);
  const [isSidebarOpen, setIsSidebarOpen] = React.useState(false);
  
  // Anonymous Identification
  const [userId, setUserId] = React.useState<string>("anonymous");
  const [sessionId, setSessionId] = React.useState<string>("default");

  // Model Settings
  const [settings, setSettings] = React.useState<AppSettings>({
    provider: "google",
    googleApiKey: "",
    googleModel: "gemini-3.1-flash-lite-preview",
  });
  const [isSettingsOpen, setIsSettingsOpen] = React.useState(false);

  // Initialize Anonymous User & Session
  React.useEffect(() => {
    // 1. Identify User
    let storedUserId = localStorage.getItem("nexus_user_id");
    if (!storedUserId) {
      storedUserId = "u-" + Math.random().toString(36).substring(2, 15);
      localStorage.setItem("nexus_user_id", storedUserId);
    }
    setUserId(storedUserId);

    // 2. Identify Current Session
    let storedSessionId = localStorage.getItem("nexus_current_session_id");
    if (!storedSessionId) {
      storedSessionId = "s-" + Date.now().toString(36);
      localStorage.setItem("nexus_current_session_id", storedSessionId);
    }
    setSessionId(storedSessionId);

    // 3. Load settings
    const saved = localStorage.getItem("nexus-ai-settings");
    if (saved) {
      try {
        const parsed: AppSettings = JSON.parse(saved);
        parsed.provider = "google"; // Force google
        setSettings(parsed);
      } catch (e) {}
    }
  }, []);

  // Fetch history when session changes
  React.useEffect(() => {
    if (sessionId !== "default") {
      api.getChatMessages(sessionId).then(msgs => {
        if (msgs && msgs.length > 0) {
          const formatted = msgs.map((m, i) => ({
            id: `hist-${i}`,
            role: m.role as "user" | "assistant",
            content: m.content
          }));
          setMessages(formatted);
        } else {
          setMessages([]);
        }
      });
    }
  }, [sessionId]);

  const handleSaveSettings = (newSettings: AppSettings) => {
    setSettings(newSettings);
    localStorage.setItem("nexus-ai-settings", JSON.stringify(newSettings));
  };

  const handleNewChat = () => {
    const newSid = "s-" + Date.now().toString(36);
    localStorage.setItem("nexus_current_session_id", newSid);
    setSessionId(newSid);
    setMessages([]);
    setIsSidebarOpen(false);
  };

  const handleSend = async (content: string, files: File[], retrieveOnly: boolean = false) => {
    setForwardedInput(undefined);

    if (files.length > 0) {
      for (const file of files) {
        try { await api.uploadDocument(file); } catch (err) {}
      }
    }

    if (!content.trim() && files.length > 0) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      role: "user",
      content,
    };
    setMessages((prev) => [...prev, userMessage]);
    setIsGenerating(true);

    const assistantId = (Date.now() + 1).toString();
    setMessages((prev) => [
      ...prev,
      { id: assistantId, role: "assistant", content: "...", isStreaming: true },
    ]);

    try {
      const response = await api.sendMessage(
        content,
        sessionId,
        userId,
        settings.provider,
        settings.provider === "google" ? settings.googleApiKey : undefined,
        settings.provider === "google" ? settings.googleModel : "gemini-3.1-flash-lite-preview",
        retrieveOnly
      );
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === assistantId
            ? {
              ...msg,
              content: response.reply,
              isStreaming: false,
              citations: response.citations || [],
            }
            : msg
        )
      );
    } catch (error) {
      console.error("Chat error:", error);
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === assistantId
            ? { ...msg, content: "Lỗi kết nối backend.", isStreaming: false }
            : msg
        )
      );
    } finally {
      setIsGenerating(false);
    }
  };

  const handleStop = () => {
    setIsGenerating(false);
  };

  return (
    <div className="flex h-[100dvh] bg-background overflow-hidden font-sans relative w-full">
      {/* Mobile Sidebar Overlay */}
      {isSidebarOpen && (
        <div 
          className="fixed inset-0 bg-black/60 backdrop-blur-sm z-40 md:hidden transition-opacity"
          onClick={() => setIsSidebarOpen(false)}
        />
      )}

      <Sidebar 
        isOpen={isSidebarOpen}
        setIsOpen={setIsSidebarOpen}
        onOpenSettings={() => setIsSettingsOpen(true)} 
        onNewChat={handleNewChat}
        onSelectSession={(sid) => {
          setSessionId(sid);
          localStorage.setItem("nexus_current_session_id", sid);
        }}
        userId={userId}
        currentSessionId={sessionId}
      />

      <main className="flex-1 flex flex-col min-w-0 h-[100dvh] overflow-hidden relative w-full">
        {/* Mobile Header - Truly Fixed for iOS */}
        <header className="md:hidden fixed top-0 left-0 right-0 z-50 bg-background/95 backdrop-blur-md border-b border-zinc-200 dark:border-zinc-800 safe-top">
          <div className="flex items-center justify-between p-3">
            <Button 
              variant="ghost" 
              size="icon" 
              onClick={() => setIsSidebarOpen(true)}
              className="h-10 w-10 rounded-xl hover:bg-zinc-100 dark:hover:bg-zinc-900 transition-colors"
            >
              <Menu className="h-6 w-6 text-zinc-700 dark:text-zinc-300" />
            </Button>
            <span className="font-bold text-sm tracking-tight text-zinc-800 dark:text-zinc-200">Nexus AI</span>
            <div className="w-10" /> 
          </div>
        </header>

        {/* Spacer for Fixed Header on Mobile */}
        <div className="md:hidden h-14 w-full flex-none" />

        <ChatArea messages={messages} />

        <div className="flex-none bg-background/95 backdrop-blur-md border-t border-zinc-200 dark:border-zinc-800 py-2 sm:py-4 safe-bottom">
          <ChatInput
            onSend={handleSend}
            onStop={handleStop}
            isGenerating={isGenerating}
            forwardedInput={forwardedInput}
          />
        </div>
      </main>

      <SettingsDialog
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
        onSave={handleSaveSettings}
        initialSettings={settings}
      />
    </div>
  );
}
