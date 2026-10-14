import { ChevronLeft, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

export const PAGE_SIZES = ["10", "25", "50", "100", "all"];

function pageList(page, pages) {
  const set = new Set([1, pages, page - 1, page, page + 1].filter((p) => p >= 1 && p <= pages));
  const sorted = [...set].sort((a, b) => a - b);
  const out = [];
  sorted.forEach((p, i) => { if (i && p - sorted[i - 1] > 1) out.push("…" + p); out.push(p); });
  return out;
}

export function Pagination({ total, page, pageSize, onPage, onPageSize }) {
  const size = pageSize === "all" ? total || 1 : Number(pageSize);
  const pages = Math.max(1, Math.ceil(total / size));
  const from = total ? (page - 1) * size + 1 : 0;
  const to = Math.min(total, page * size);
  return (
    <div className="flex flex-col sm:flex-row sm:items-center gap-3 px-4 sm:px-6 py-3 border-t border-[#E7E0D6] bg-[#F4EFE6]/50" data-testid="library-pagination">
      <div className="flex items-center gap-2 text-sm text-stone-600">
        <span>Show</span>
        <Select value={pageSize} onValueChange={onPageSize}>
          <SelectTrigger className="w-[90px] h-8 bg-[#FFFDF9]" data-testid="library-page-size-select"><SelectValue /></SelectTrigger>
          <SelectContent>
            {PAGE_SIZES.map((s) => <SelectItem key={s} value={s} data-testid={`page-size-${s}`}>{s === "all" ? "All" : s}</SelectItem>)}
          </SelectContent>
        </Select>
        <span className="f-mono text-xs" data-testid="library-page-range">{from}–{to} of {total}</span>
      </div>
      {pages > 1 && (
        <div className="sm:ml-auto flex items-center gap-1">
          <Button variant="ghost" size="icon" className="h-8 w-8" disabled={page <= 1} onClick={() => onPage(page - 1)} data-testid="library-page-prev"><ChevronLeft className="h-4 w-4" /></Button>
          {pageList(page, pages).map((p) => typeof p === "string" ? <span key={p} className="px-1 text-stone-400">…</span> : (
            <Button key={p} variant={p === page ? "default" : "ghost"} size="sm" className="h-8 min-w-8 px-2" onClick={() => onPage(p)} data-testid={`library-page-${p}`}>{p}</Button>
          ))}
          <Button variant="ghost" size="icon" className="h-8 w-8" disabled={page >= pages} onClick={() => onPage(page + 1)} data-testid="library-page-next"><ChevronRight className="h-4 w-4" /></Button>
        </div>
      )}
    </div>
  );
}
