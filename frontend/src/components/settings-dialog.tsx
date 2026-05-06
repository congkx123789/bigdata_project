"use client";
import * as React from "react";
import { X, Settings, Cpu, Globe, Key, Save, AlertCircle } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

interface SettingsDialogProps {
  isOpen: boolean;
  onClose: () => void;
  onSave: (settings: AppSettings) => void;
  initialSettings: AppSettings;
}

export interface AppSettings {
  provider: "local" | "google";
  googleApiKey: string;
  googleModel: string;
}

export function SettingsDialog({ isOpen, onClose, onSave, initialSettings }: SettingsDialogProps) {
  const [settings, setSettings] = React.useState<AppSettings>(initialSettings);
  const [showSaved, setShowSaved] = React.useState(false);

  React.useEffect(() => {
    if (isOpen) {
      setSettings(initialSettings);
      setShowSaved(false);
    }
  }, [isOpen, initialSettings]);

  const handleSave = () => {
    onSave(settings);
    setShowSaved(true);
    setTimeout(() => {
      setShowSaved(false);
      onClose();
    }, 1000);
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 bg-black/40 backdrop-blur-[2px] z-[100]"
          />

          {/* Dialog */}
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 20 }}
            className="fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-full max-w-md bg-zinc-950 border border-zinc-800 rounded-2xl shadow-2xl z-[101] overflow-hidden"
          >
            <div className="flex items-center justify-between p-5 border-b border-zinc-800 bg-zinc-950/50 backdrop-blur-xl">
              <div className="flex items-center gap-2">
                <Settings className="h-5 w-5 text-zinc-400" />
                <h2 className="font-bold text-zinc-100 uppercase tracking-tight text-xs">Cấu hình mô hình AI</h2>
              </div>
              <Button variant="ghost" size="icon" onClick={onClose} className="h-8 w-8 text-zinc-500 hover:text-zinc-100">
                <X className="h-4 w-4" />
              </Button>
            </div>

            <div className="p-6 space-y-8 max-h-[70vh] overflow-y-auto scrollbar-thin scrollbar-thumb-zinc-800">
              {/* Provider Selection (Tạm thời ẩn theo yêu cầu) */}
              <div className="hidden space-y-4">
                <label className="text-[10px] font-black text-zinc-500 uppercase tracking-widest">Nguồn xử lý (Provider)</label>
                <div className="grid grid-cols-2 gap-4">
                  <button
                    onClick={() => setSettings({ ...settings, provider: "local" })}
                    className={cn(
                      "flex flex-col items-center gap-3 p-5 rounded-xl border transition-all duration-300",
                      settings.provider === "local"
                        ? "bg-zinc-100 text-zinc-950 border-zinc-100 shadow-[0_0_20px_rgba(255,255,255,0.1)]"
                        : "bg-zinc-900/50 border-zinc-800 text-zinc-500 hover:border-zinc-700 hover:text-zinc-300"
                    )}
                  >
                    <Cpu className={cn("h-6 w-6", settings.provider === "local" ? "animate-pulse" : "")} />
                    <span className="text-xs font-bold">Chạy tại máy</span>
                  </button>
                  <button
                    onClick={() => setSettings({ ...settings, provider: "google" })}
                    className={cn(
                      "flex flex-col items-center gap-3 p-5 rounded-xl border transition-all duration-300",
                      settings.provider === "google"
                        ? "bg-zinc-100 text-zinc-950 border-zinc-100 shadow-[0_0_20px_rgba(255,255,255,0.1)]"
                        : "bg-zinc-900/50 border-zinc-800 text-zinc-500 hover:border-zinc-700 hover:text-zinc-300"
                    )}
                  >
                    <Globe className={cn("h-6 w-6", settings.provider === "google" ? "animate-spin-slow" : "")} />
                    <span className="text-xs font-bold">Google Gemini</span>
                  </button>
                </div>
              </div>

              {/* API Key Input & Model selection */}
              <AnimatePresence mode="wait">
                {settings.provider === "google" && (
                  <motion.div
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -10 }}
                    className="space-y-6"
                  >
                    <div className="space-y-3">
                      <div className="flex items-center justify-between">
                        <label className="text-[10px] font-black text-zinc-500 uppercase tracking-widest flex items-center gap-1">
                          <Key className="h-3 w-3" /> Google API Key
                        </label>
                        <a 
                          href="https://aistudio.google.com/app/apikey" 
                          target="_blank" 
                          className="text-[10px] text-zinc-500 hover:text-blue-400 transition-colors"
                        >
                          Lấy mã tại đây →
                        </a>
                      </div>
                      <Input
                        type="password"
                        placeholder="Để trống để dùng key hệ thống mặc định..."
                        value={settings.googleApiKey}
                        onChange={(e) => setSettings({ ...settings, googleApiKey: e.target.value })}
                        className="bg-zinc-900 border-zinc-800 text-zinc-100 h-12 focus-visible:ring-zinc-400 rounded-xl placeholder:text-zinc-600"
                      />
                      <p className="text-[10px] text-zinc-500 italic">
                        * Hệ thống đã tích hợp sẵn Key tốc độ cao. Bạn chỉ cần nhập Key riêng nếu muốn dùng hạn mức cá nhân.
                      </p>
                    </div>

                    <div className="space-y-4">
                      <label className="text-[10px] font-black text-zinc-500 uppercase tracking-widest">Phiên bản Gemini (Free Tier 2026)</label>
                      <div className="grid grid-cols-1 gap-3">
                        {[
                          { id: "gemini-3.1-flash-lite-preview", name: "Gemini 3.1 Flash-Lite", desc: "Mới nhất (2026), cực nhanh, hạn mức cao" },
                          { id: "gemini-3-flash-preview", name: "Gemini 3 Flash", desc: "Cân bằng trí tuệ & tốc độ, đa năng" },
                          { id: "gemini-2.5-flash", name: "Gemini 2.5 Flash", desc: "Thế hệ 2.5 ổn định, tin cậy" },
                          { id: "gemini-2.5-flash-lite", name: "Gemini 2.5 Flash-Lite", desc: "Tối ưu hóa chi phí & tốc độ" },
                        ].map((m) => (
                          <button
                            key={m.id}
                            onClick={() => setSettings({ ...settings, googleModel: m.id })}
                            className={cn(
                              "flex flex-col items-start p-4 rounded-xl border transition-all duration-300 text-left group",
                              settings.googleModel === m.id
                                ? "bg-zinc-100 border-zinc-100 text-zinc-950 shadow-lg"
                                : "bg-zinc-900/50 border-zinc-800 text-zinc-400 hover:border-zinc-600 hover:bg-zinc-800/50"
                            )}
                          >
                            <span className="text-base font-black tracking-tight">{m.name}</span>
                            <span className={cn(
                              "text-xs font-medium leading-relaxed",
                              settings.googleModel === m.id ? "text-zinc-600" : "text-zinc-500"
                            )}>{m.desc}</span>
                          </button>
                        ))}
                      </div>
                      
                      {/* Custom Model Input */}
                      <div className="mt-6 pt-6 border-t border-zinc-800 space-y-3">
                        <label className="text-[10px] font-black text-zinc-500 uppercase tracking-widest">Hoặc nhập Model ID tùy chỉnh</label>
                        <Input
                          placeholder="ví dụ: gemini-3.1-pro-preview"
                          value={settings.googleModel}
                          onChange={(e) => setSettings({ ...settings, googleModel: e.target.value })}
                          className="h-12 text-base bg-zinc-900 border-zinc-800 text-zinc-100 focus-visible:ring-zinc-400 rounded-lg"
                        />
                      </div>
                    </div>

                    <div className="space-y-3">
                      <div className="flex gap-3 p-4 rounded-xl bg-amber-950/10 border border-amber-900/20">
                        <AlertCircle className="h-4 w-4 text-amber-500 shrink-0 mt-0.5" />
                        <p className="text-[10px] text-amber-600/80 leading-relaxed">
                          <strong className="text-amber-500 uppercase tracking-tighter mr-1">Lưu ý:</strong> Dữ liệu có thể được Google sử dụng để huấn luyện theo chính sách Free Tier.
                        </p>
                      </div>
                      <div className="flex gap-3 p-4 rounded-xl bg-zinc-900 border border-zinc-800">
                        <Globe className="h-4 w-4 text-zinc-600 shrink-0 mt-0.5" />
                        <p className="text-[10px] text-zinc-500 leading-relaxed">
                          Dữ liệu pháp luật được gửi trực tiếp từ máy chủ tới Google API để tối ưu phản hồi.
                        </p>
                      </div>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>

            <div className="p-5 border-t border-zinc-800 flex justify-end gap-3 bg-zinc-950">
              <Button variant="ghost" onClick={onClose} className="text-zinc-400 hover:text-zinc-100 hover:bg-zinc-900">Hủy</Button>
              <Button 
                onClick={handleSave}
                disabled={showSaved}
                className={cn(
                  "min-w-[140px] h-10 rounded-xl font-bold transition-all duration-500",
                  showSaved 
                    ? "bg-green-500 text-white shadow-[0_0_20px_rgba(34,197,94,0.3)]" 
                    : "bg-zinc-100 text-zinc-900 hover:bg-white"
                )}
              >
                {showSaved ? (
                  <div className="flex items-center gap-2">
                    <Save className="h-4 w-4 animate-bounce" />
                    <span>Đã lưu</span>
                  </div>
                ) : (
                  "Lưu thay đổi"
                )}
              </Button>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
