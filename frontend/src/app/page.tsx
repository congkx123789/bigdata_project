"use client";

import * as React from "react";
import { Sidebar } from "@/components/sidebar";
import { ChatArea } from "@/components/chat-area";
import { ChatInput } from "@/components/chat-input";
import { DocumentViewer } from "@/components/document-viewer";
import { api } from "@/lib/api";
import {
  Panel,
  Group as PanelGroup,
  Separator as PanelResizeHandle,
} from "react-resizable-panels";
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

  const handleQuote = (text: string) => {
    setForwardedInput(text);
  };

  const handleQuickSend = (text: string) => {
    handleSend(`Phân tích đoạn văn bản này giúp tôi: \n\n> ${text}`, []);
  };

  return (
    <div className="flex h-screen bg-background overflow-hidden">
      <Sidebar />

      <main className="flex-1 flex flex-col relative min-w-0">
        <PanelGroup orientation="horizontal" className="h-full">
          {/* Left: Document Viewer */}
          <Panel defaultSize={55} minSize={30}>
            <DocumentViewer
              onQuote={handleQuote}
              onSend={handleQuickSend}
            />
          </Panel>

          <PanelResizeHandle className="bg-zinc-200 dark:bg-zinc-800 w-1.5 hover:bg-blue-500/50 transition-colors cursor-col-resize" />

          {/* Right: Chat Interface */}
          <Panel defaultSize={45} minSize={25}>
            <div className="flex flex-col h-full relative border-l border-zinc-200 dark:border-zinc-800">
              <ChatArea messages={messages} />

              <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-background via-background to-transparent pt-10">
                <ChatInput
                  onSend={handleSend}
                  onStop={handleStop}
                  isGenerating={isGenerating}
                  forwardedInput={forwardedInput}
                />
              </div>
            </div>
          </Panel>
        </PanelGroup>
      </main>
    </div>
  );
}
