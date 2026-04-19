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
  citations?: Array<{ id: number; source: string; page?: number }>;
  isStreaming?: boolean;
}

import { AppSettings, SettingsDialog } from "@/components/settings-dialog";

export default function Home() {
  const [messages, setMessages] = React.useState<Message[]>([]);
  const [isGenerating, setIsGenerating] = React.useState(false);
  const [forwardedInput, setForwardedInput] = React.useState<string | undefined>(undefined);
  
  // Model Settings
  const [settings, setSettings] = React.useState<AppSettings>({
    provider: "local",
    googleApiKey: "",
  });
  const [isSettingsOpen, setIsSettingsOpen] = React.useState(false);

  // Load settings from localStorage on mount
  React.useEffect(() => {
    const saved = localStorage.getItem("nexus-ai-settings");
    if (saved) {
      try {
        const parsed: AppSettings = JSON.parse(saved);
        // Ưu tiên chọn Google nếu có Key để giảm tải GPU local theo yêu cầu
        if (parsed.googleApiKey && parsed.googleApiKey.trim() !== "") {
          parsed.provider = "google";
        }
        setSettings(parsed);
      } catch (e) {
        console.error("Failed to parse settings", e);
      }
    }
  }, []);

  const handleSaveSettings = (newSettings: AppSettings) => {
    setSettings(newSettings);
    localStorage.setItem("nexus-ai-settings", JSON.stringify(newSettings));
  };

  const handleSend = async (content: string, files: File[], retrieveOnly: boolean = false) => {
    setForwardedInput(undefined); // Reset forwarded input when sent

    if (files.length > 0) {
      for (const file of files) {
        try {
          await api.uploadDocument(file);
        } catch (err) {
          console.error("Upload failed for file:", file.name, err);
        }
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
      {
        id: assistantId,
        role: "assistant",
        content: "...",
        isStreaming: true,
      },
    ]);

    try {
      const response = await api.sendMessage(
        content,
        "default",
        settings.provider,
        settings.provider === "google" ? settings.googleApiKey : undefined,
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
            ? {
              ...msg,
              content: "Xin lỗi, hiện tại tôi không thể kết nối tới backend. Vui lòng thử lại sau.",
              isStreaming: false,
            }
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
    <div className="flex h-screen bg-background overflow-hidden font-sans">
      <Sidebar onOpenSettings={() => setIsSettingsOpen(true)} />

      <main className="flex-1 flex flex-col min-w-0">
        <ChatArea messages={messages} />

        <div className="bg-background border-t border-zinc-200 dark:border-zinc-800 py-4">
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
