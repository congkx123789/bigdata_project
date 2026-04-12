"use client";

const CORE_API_BASE_URL = "/api";

export interface ChatHistoryGroup {
    label: string;
    chats: Array<{ id: number; title: string }>;
}

export interface ChatResponse {
    reply: string;
    session_id: string;
    citations?: Array<{ id: number; source: string; page?: number }>;
}

export const api = {
    async getChatHistory(): Promise<ChatHistoryGroup[]> {
        try {
            const resp = await fetch(`${CORE_API_BASE_URL}/chats/history`);
            if (!resp.ok) throw new Error("Failed to fetch history");
            const data = await resp.json();
            return data.groups;
        } catch (error) {
            console.error("History fetch error:", error);
            return [];
        }
    },

    async sendMessage(message: string, sessionId: string = "default"): Promise<ChatResponse> {
        const resp = await fetch(`${CORE_API_BASE_URL}/chats/send`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ message, session_id: sessionId }),
        });
        if (!resp.ok) throw new Error("Failed to send message");
        return await resp.json();
    },

    async uploadDocument(file: File) {
        const formData = new FormData();
        formData.append("file", file);

        const resp = await fetch(`${CORE_API_BASE_URL}/documents/upload`, {
            method: "POST",
            body: formData,
        });
        if (!resp.ok) throw new Error("Upload failed");
        return await resp.json();
    }
};
