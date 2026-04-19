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
            className="fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-full max-w-md bg-zinc-50 dark:bg-zinc-950 border border-zinc-200 dark:border-zinc-800 rounded-xl shadow-2xl z-[101] overflow-hidden"
          >
            <div className="flex items-center justify-between p-4 border-b">
              <div className="flex items-center gap-2">
                <Settings className="h-5 w-5 text-zinc-500" />
                <h2 className="font-semibold text-zinc-900 dark:text-zinc-100 uppercase tracking-tight text-sm">Cấu hình mô hình AI</h2>
              </div>
              <Button variant="ghost" size="icon" onClick={onClose} className="h-8 w-8">
                <X className="h-4 w-4" />
              </Button>
            </div>

            <div className="p-6 space-y-6">
              {/* Provider Selection */}
              <div className="space-y-3">
                <label className="text-xs font-bold text-zinc-500 uppercase tracking-wider">Nguồn xử lý (Provider)</label>
                <div className="grid grid-cols-2 gap-3">
                  <button
                    onClick={() => setSettings({ ...settings, provider: "local" })}
                    className={cn(
                      "flex flex-col items-center gap-2 p-4 rounded-lg border transition-all text-sm",
                      settings.provider === "local"
                        ? "bg-zinc-900 text-zinc-50 border-zinc-900 dark:bg-zinc-50 dark:text-zinc-950 dark:border-zinc-50"
                        : "bg-transparent border-zinc-200 dark:border-zinc-800 text-zinc-500 hover:border-zinc-400 dark:hover:border-zinc-600"
                    )}
                  >
                    <Cpu className="h-5 w-5" />
                    <span>Chạy tại máy (Local)</span>
                  </button>
                  <button
                    onClick={() => setSettings({ ...settings, provider: "google" })}
                    className={cn(
                      "flex flex-col items-center gap-2 p-4 rounded-lg border transition-all text-sm",
                      settings.provider === "google"
                        ? "bg-zinc-900 text-zinc-50 border-zinc-900 dark:bg-zinc-50 dark:text-zinc-950 dark:border-zinc-50"
                        : "bg-transparent border-zinc-200 dark:border-zinc-800 text-zinc-500 hover:border-zinc-400 dark:hover:border-zinc-600"
                    )}
                  >
                    <Globe className="h-5 w-5" />
                    <span>Google Gemini</span>
                  </button>
                </div>
              </div>

              {/* API Key Input */}
              <AnimatePresence mode="wait">
                {settings.provider === "google" && (
                  <motion.div
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: "auto" }}
                    exit={{ opacity: 0, height: 0 }}
                    className="space-y-3 overflow-hidden"
                  >
                    <div className="flex items-center justify-between">
                      <label className="text-xs font-bold text-zinc-500 uppercase tracking-wider flex items-center gap-1">
                        <Key className="h-3 w-3" /> Google API Key
                      </label>
                      <a 
                        href="https://aistudio.google.com/app/apikey" 
                        target="_blank" 
                        className="text-[10px] text-zinc-400 hover:text-zinc-600 underline"
                      >
                        Lấy Key tại đây
                      </a>
                    </div>
                    <Input
                      type="password"
                      placeholder="AIzaSy..."
                      value={settings.googleApiKey}
                      onChange={(e) => setSettings({ ...settings, googleApiKey: e.target.value })}
                      className="bg-zinc-100 dark:bg-zinc-900 border-zinc-200 dark:border-zinc-800 focus-visible:ring-zinc-400"
                    />
                    <div className="flex gap-2 p-3 rounded-md bg-amber-50 dark:bg-amber-950/20 border border-amber-200/50 dark:border-amber-900/30">
                      <AlertCircle className="h-4 w-4 text-amber-600 shrink-0" />
                      <p className="text-[10px] text-amber-700 dark:text-amber-500">
                        API Key sẽ được lưu trong trình duyệt của bạn. Nó được dùng để gửi yêu cầu tới Google thông qua backend Nexus.
                      </p>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>

            <div className="p-4 border-t flex justify-end gap-3 bg-zinc-100/50 dark:bg-zinc-900/50">
              <Button variant="ghost" onClick={onClose}>Hủy</Button>
              <Button 
                onClick={handleSave}
                disabled={showSaved}
                className={cn(
                  "min-w-[100px] transition-all",
                  showSaved && "bg-green-600 hover:bg-green-600"
                )}
              >
                {showSaved ? (
                  <Save className="h-4 w-4 animate-bounce" />
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
