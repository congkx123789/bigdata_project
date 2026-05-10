"use client";

const CORE_API_BASE_URL = "/api";

export interface ChatHistoryGroup {
    label: string;
    chats: Array<{ id: number; title: string }>;
}

export interface ChatResponse {
    reply: string;
    session_id: string;
    citations?: Array<{ id: number; source: string; page?: number; content?: string; summary?: string }>;
}

export const api = {
    async getSessionList(userId: string = "anonymous"): Promise<any[]> {
        try {
            const resp = await fetch(`${CORE_API_BASE_URL}/chats/list?user_id=${userId}`);
            if (!resp.ok) throw new Error("Failed to fetch session list");
            const data = await resp.json();
            return data.sessions;
        } catch (error) {
            console.error("Session list fetch error:", error);
            return [];
        }
    },

    async getChatMessages(sessionId: string): Promise<any[]> {
        try {
            const resp = await fetch(`${CORE_API_BASE_URL}/chats/history?session_id=${sessionId}`);
            if (!resp.ok) throw new Error("Failed to fetch messages");
            const data = await resp.json();
            return data.messages;
        } catch (error) {
            console.error("History fetch error:", error);
            return [];
        }
    },

    async sendMessage(
        message: string,
        sessionId: string = "default",
        userId: string = "anonymous",
        provider: string = "google",
        apiKey?: string,
        googleModel: string = "gemini-3.1-flash-lite-preview",
        retrieveOnly: boolean = false
    ): Promise<ChatResponse> {
        const resp = await fetch(`${CORE_API_BASE_URL}/chats/send`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                message,
                session_id: sessionId,
                user_id: userId,
                provider,
                api_key: apiKey,
                google_model: googleModel,
                retrieve_only: retrieveOnly
            }),
        });
        if (!resp.ok) throw new Error("Failed to send message");
        return await resp.json();
    },

    async *sendMessageStream(
        message: string,
        sessionId: string = "default",
        userId: string = "anonymous",
        provider: string = "google",
        apiKey?: string,
        googleModel: string = "gemini-3.1-flash-lite-preview"
    ): AsyncGenerator<string> {
        const resp = await fetch(`${CORE_API_BASE_URL}/chats/send_stream`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                message,
                session_id: sessionId,
                user_id: userId,
                provider,
                api_key: apiKey,
                google_model: googleModel
            }),
        });
        
        if (!resp.ok) throw new Error("Streaming failed");
        
        const reader = resp.body?.getReader();
        if (!reader) throw new Error("ReadableStream not supported");
        
        const decoder = new TextDecoder();
        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            const chunk = decoder.decode(value, { stream: true });
            console.log("DEBUG: Frontend nhận chunk:", chunk);
            yield chunk;
        }
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
