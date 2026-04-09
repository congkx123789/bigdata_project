"use client";

import * as React from "react";
import { ScrollArea } from "@/components/ui/scroll-area";
import { FloatingMenu } from "./floating-menu";
import { cn } from "@/lib/utils";
import { FileText, Download, Maximize2 } from "lucide-react";

interface DocumentViewerProps {
    className?: string;
    onQuote: (text: string) => void;
    onSend: (text: string) => void;
}

export function DocumentViewer({ className, onQuote, onSend }: DocumentViewerProps) {
    const [selectedText, setSelectedText] = React.useState("");
    const [menuPosition, setMenuPosition] = React.useState<{ x: number; y: number } | null>(null);
    const containerRef = React.useRef<HTMLDivElement>(null);

    const handleMouseUp = () => {
        const selection = window.getSelection();
        const text = selection?.toString().trim();

        if (text && text.length > 0) {
            const range = selection?.getRangeAt(0);
            const rect = range?.getBoundingClientRect();

            if (rect) {
                setSelectedText(text);
                setMenuPosition({
                    x: rect.left + rect.width / 2,
                    y: rect.top - 10,
                });
            }
        } else {
            setMenuPosition(null);
        }
    };

    const handleAction = (action: string) => {
        if (action === "quote") onQuote(selectedText);
        if (action === "send") onSend(selectedText);
        // Other actions (summarize/translate) can be added here
        setMenuPosition(null);
        window.getSelection()?.removeAllRanges();
    };

    return (
        <div className={cn("flex flex-col h-full bg-zinc-100 dark:bg-zinc-900", className)} ref={containerRef}>
            {/* Doc Header */}
            <div className="flex items-center justify-between px-4 py-2 border-b bg-white dark:bg-zinc-950">
                <div className="flex items-center gap-2">
                    <FileText className="h-4 w-4 text-blue-500" />
                    <span className="text-sm font-medium truncate max-w-[200px]">Vietnam_Digital_Economy_Report_2024.pdf</span>
                </div>
                <div className="flex items-center gap-1">
                    <button className="p-1.5 hover:bg-zinc-200 dark:hover:bg-zinc-800 rounded transition-colors">
                        <Download className="h-4 w-4 text-zinc-500" />
                    </button>
                    <button className="p-1.5 hover:bg-zinc-200 dark:hover:bg-zinc-800 rounded transition-colors">
                        <Maximize2 className="h-4 w-4 text-zinc-500" />
                    </button>
                </div>
            </div>

            {/* Doc Content */}
            <ScrollArea className="flex-1 p-8" onMouseUp={handleMouseUp}>
                <div className="max-w-3xl mx-auto bg-white dark:bg-zinc-950 shadow-sm border p-12 min-h-[1000px] prose dark:prose-invert">
                    <h1>Báo cáo Kinh tế số Việt Nam 2024</h1>
                    <p className="text-zinc-500 mb-8 italic">Phát hành bởi Bộ Công Thương và Hiệp hội Thương mại điện tử Việt Nam (VECOM)</p>

                    <h3>1. Tổng quan thị trường</h3>
                    <p>
                        Kinh tế số Việt Nam tiếp tục duy trì đà tăng trưởng mạnh mẽ trong năm 2024. Tổng giá trị hàng hóa (GMV) của nền kinh tế số dự kiến đạt **45 tỷ USD**, tăng trưởng 20% so với năm 2023. Trong đó, thương mại điện tử vẫn là động lực tăng trưởng chính, đóng góp gần 65% tổng giá trị GMV.
                    </p>

                    <h3>2. Chuyển đổi số trong doanh nghiệp</h3>
                    <p>
                        Tỷ lệ doanh nghiệp SME (vừa và nhỏ) ứng dụng các giải pháp phần mềm quản lý (ERP, CRM) và nền tảng đám mây đã tăng từ 35% lên **52%**. Đặc biệt, sự bùng nổ của Trí tuệ nhân tạo (AI) đã bắt đầu tác động sâu rộng đến quy trình vận hành và tối ưu hóa chi phí cho các doanh nghiệp logistics và bán lẻ.
                    </p>

                    <blockquote>
                        "AI không còn là một xu hướng xa vời, mà đã trở thành công cụ bắt buộc để các doanh nghiệp Việt Nam duy trì lợi thế cạnh tranh trong kỷ nguyên số."
                    </blockquote>

                    <h3>3. Cơ sở hạ tầng dữ liệu</h3>
                    <p>
                        Việc triển khai các trung tâm dữ liệu (Data Center) quy mô lớn đạt tiêu chuẩn Tier III đang được đẩy nhanh. Việt Nam đang dần trở thành một "Digital Hub" của khu vực Đông Nam Á nhờ vào vị trí địa lý thuận lợi và chi phí vận hành ngày càng tối ưu. Những nỗ lực của chính phủ trong việc bóc tách dữ liệu và quản trị dữ liệu lớn (Big Data) thông qua các công nghệ như Spark và Delta Lake đang mang lại những hiệu quả rõ rệt.
                    </p>

                    <img
                        src="https://images.unsplash.com/photo-1551288049-bebda4e38f71?auto=format&fit=crop&q=80&w=1000"
                        alt="Data Analytics Visualization"
                        className="rounded-lg shadow-md my-8 w-full h-[400px] object-cover"
                    />

                    <h3>4. Thách thức và Định hướng</h3>
                    <p>
                        Mặc dù có nhiều tiềm năng, nhưng vấn đề bảo mật dữ liệu và nguồn nhân lực chất lượng cao vẫn là rào cản lớn. Định hướng đến năm 2030, Việt Nam đặt mục tiêu kinh tế số đóng góp **30% GDP**. Để đạt được điều này, việc hoàn thiện khung pháp lý và bảo vệ quyền lợi người dùng trên không gian mạng là ưu tiên hàng đầu.
                    </p>
                </div>
            </ScrollArea>

            <FloatingMenu
                position={menuPosition}
                selectedText={selectedText}
                onAction={handleAction}
            />
        </div>
    );
}
