import { Download, FileText } from 'lucide-react';

interface Props {
  onExportPdf: () => void;
  onExportXlsx: () => void;
}

export function ReportFooter({ onExportPdf, onExportXlsx }: Props) {
  return (
    <footer className="mt-16 pt-8 border-t border-zinc-700">
      <div className="flex justify-between items-center">
        <div className="text-xs text-zinc-500">
          SPOTTER v1.0 · 마포구 프랜차이즈 입지 시뮬레이터
        </div>
        <div className="flex gap-2">
          <button
            onClick={onExportPdf}
            className="flex items-center gap-2 rounded-md border border-zinc-700 px-4 py-2 text-sm text-zinc-300 hover:bg-zinc-700"
          >
            <FileText className="w-4 h-4" /> PDF
          </button>
          <button
            onClick={onExportXlsx}
            className="flex items-center gap-2 rounded-md border border-zinc-700 px-4 py-2 text-sm text-zinc-300 hover:bg-zinc-700"
          >
            <Download className="w-4 h-4" /> XLSX
          </button>
        </div>
      </div>
    </footer>
  );
}
