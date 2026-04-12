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

export default function Home() {
  const [messages, setMessages] = React.useState<Message[]>([]);
  const [isGenerating, setIsGenerating] = React.useState(false);
  const [forwardedInput, setForwardedInput] = React.useState<string | undefined>(undefined);

  const handleSend = async (content: string, files: File[]) => {
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
      const response = await api.sendMessage(content);
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
      <Sidebar />

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
    </div>
  );
}
