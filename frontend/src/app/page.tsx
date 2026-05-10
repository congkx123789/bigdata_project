"use client";

import * as React from "react";
import { flushSync } from "react-dom";
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
  isThinking?: boolean;
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
    googleModel: "gemini-2.0-flash",
  });
  const [isSettingsOpen, setIsSettingsOpen] = React.useState(false);

  // Initialize Anonymous User & Session
  React.useEffect(() => {
    // 1. VH Fix for Mobile
    const setVH = () => {
      let vh = window.innerHeight * 0.01;
      document.documentElement.style.setProperty('--vh', `${vh}px`);
    };
    setVH();
    window.addEventListener('resize', setVH);

    // 2. Identify User
    let storedUserId = localStorage.getItem("nexus_user_id");
    if (!storedUserId) {
      storedUserId = "u-" + Math.random().toString(36).substring(2, 15);
      localStorage.setItem("nexus_user_id", storedUserId);
    }
    setUserId(storedUserId);

    // 3. Identify Current Session
    let storedSessionId = localStorage.getItem("nexus_current_session_id");
    if (!storedSessionId) {
      storedSessionId = "s-" + Date.now().toString(36);
      localStorage.setItem("nexus_current_session_id", storedSessionId);
    }
    setSessionId(storedSessionId);

    // 4. Load settings
    const saved = localStorage.getItem("nexus-ai-settings");
    if (saved) {
      try {
        const parsed: AppSettings = JSON.parse(saved);
        parsed.provider = "google"; // Force google
        setSettings(parsed);
      } catch (e) { }
    }

    return () => window.removeEventListener('resize', setVH);
  }, []);

  // Fetch history when session changes
  React.useEffect(() => {
    if (sessionId !== "default") {
      api.getChatMessages(sessionId).then(msgs => {
        if (msgs && msgs.length > 0) {
          const formatted = msgs.map((m, i) => {
            let citations = m.citations;
            if (m.role === "assistant" && (!citations || citations.length === 0)) {
              try {
                // Regex mở rộng để bắt cả JSON trong ```json ... ``` hoặc [CITATIONS_JSON]...
                const jsonMatch = m.content.match(/(?:```(?:json)?\s*)?\[\s*\{[\s\S]*\}\s*\](?:\s*```)?\s*$/) ||
                  m.content.match(/\[CITATIONS_JSON\]([\s\S]*?)\[\/CITATIONS_JSON\]/);

                if (jsonMatch) {
                  const rawJson = jsonMatch[1] || jsonMatch[0].replace(/```(?:json)?|```/g, "").trim();
                  citations = JSON.parse(rawJson);
                }
              } catch (e) { }
            }
            return {
              id: `hist-${i}`,
              role: m.role as "user" | "assistant",
              content: m.content,
              citations: citations
            };
          });
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
        try { await api.uploadDocument(file); } catch (err) { }
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
      { id: assistantId, role: "assistant", content: "", isStreaming: true },
    ]);

    try {
      let fullReply = "";
      const stream = api.sendMessageStream(
        content,
        sessionId,
        userId,
        settings.provider,
        settings.provider === "google" ? settings.googleApiKey : undefined,
        settings.provider === "google" ? settings.googleModel : "gemini-2.0-flash"
      );

      for await (const chunk of stream) {
        if (!chunk || chunk === "undefined") continue;
        fullReply += chunk;

        // SỬ DỤNG FLUSHSYNC ĐỂ ÉP REACT RENDER NGAY LẬP TỨC
        flushSync(() => {
          setMessages((currentMessages) => {
            const index = currentMessages.findIndex(m => m.id === assistantId);
            if (index === -1) return currentMessages;

            const updatedMessages = [...currentMessages];
            const isThinking = fullReply.includes("🛡️") && !fullReply.includes("---");

            // Tách nội dung văn bản và phần JSON trích dẫn
            const parts = fullReply.split("[CITATIONS_JSON]");
            const cleanText = parts[0];
            let citations = updatedMessages[index].citations;

            if (parts.length > 1 && parts[1].includes("[/CITATIONS_JSON]")) {
              const citationsPart = parts[1].split("[/CITATIONS_JSON]")[0].trim();
              try {
                citations = JSON.parse(citationsPart);
              } catch (e) { }
            }

            updatedMessages[index] = {
              ...updatedMessages[index],
              content: cleanText,
              citations: citations,
              isThinking: isThinking
            };

            return updatedMessages;
          });
        });
      }

      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === assistantId
            ? {
              ...msg,
              isStreaming: false,
              // Citations will be loaded on next F5 or if we implement a final message event
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
    <div
      className="flex w-full bg-background overflow-hidden font-sans relative"
      style={{ height: 'calc(var(--vh, 1vh) * 100)' }}
    >
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

      <main
        className="flex-1 grid grid-rows-[auto_1fr_auto] min-w-0 overflow-hidden relative bg-zinc-50/50 dark:bg-zinc-950/50 safe-top"
        style={{ height: 'calc(var(--vh, 1vh) * 100)' }}
      >
        {/* Unified Header - Row 1 */}
        <header className="bg-background/80 backdrop-blur-xl border-b border-zinc-200 dark:border-zinc-800 transition-all duration-300 z-10">
          <div className="max-w-6xl mx-auto flex items-center justify-between p-3 md:p-4">
            <div className="flex items-center gap-3">
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setIsSidebarOpen(true)}
                className="h-10 w-10 rounded-xl hover:bg-zinc-100 dark:hover:bg-zinc-900 transition-colors md:hidden"
              >
                <Menu className="h-6 w-6 text-zinc-700 dark:text-zinc-300" />
              </Button>
              <div className="flex items-center gap-2">
                <div className="h-8 w-8 rounded-lg bg-blue-600 flex items-center justify-center shadow-lg shadow-blue-500/20">
                  <span className="text-white font-black text-xs">NX</span>
                </div>
                <div className="flex flex-col">
                  <span className="font-bold text-sm tracking-tight text-zinc-800 dark:text-zinc-200 leading-none">Nexus Legal AI</span>
                  <span className="text-[10px] text-zinc-500 font-medium uppercase tracking-widest mt-0.5">RAG V15 • Gold Standard</span>
                </div>
              </div>
            </div>

            <div className="flex items-center gap-2">
              {/* Desktop indicator */}
              <div className="hidden md:flex items-center gap-2 px-3 py-1.5 rounded-full bg-zinc-100 dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800">
                <div className="h-1.5 w-1.5 rounded-full bg-green-500 animate-pulse" />
                <span className="text-[10px] font-bold text-zinc-600 dark:text-zinc-400 uppercase tracking-tight">Hệ thống sẵn sàng</span>
              </div>
            </div>
          </div>
        </header>

        {/* Chat Content Area - Row 2 */}
        <div className="relative overflow-hidden flex flex-col min-h-0 h-full">
          <ChatArea messages={messages} />
        </div>

        {/* Fixed Bottom Input Area - Row 3 */}
        <div className="bg-background/80 backdrop-blur-xl border-t border-zinc-200 dark:border-zinc-800 safe-bottom z-10">
          <div className="max-w-4xl mx-auto w-full">
            <ChatInput
              onSend={handleSend}
              onStop={handleStop}
              isGenerating={isGenerating}
              forwardedInput={forwardedInput}
            />
          </div>
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
