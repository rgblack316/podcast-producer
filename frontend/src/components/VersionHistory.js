import { useState } from "react";
import { History, RotateCcw } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { api, errMsg } from "@/lib/api";
import { Markdown } from "@/components/Markdown";

const SOURCE = { ai: "AI draft", ai_revision: "AI revision", edit: "Manual edit", restore: "Restored" };

export function VersionHistory({ episode, stage, editable, onChange }) {
  const versions = [...(episode[`${stage}_versions`] || [])].reverse();
  const [selected, setSelected] = useState(null);
  const [open, setOpen] = useState(false);
  const shown = versions.find((v) => v.version === selected) || versions[0];

  const restore = async (v) => {
    try {
      const { data } = await api.post(`/episodes/${episode.id}/${stage}/restore`, { version: v });
      onChange(data);
      toast.success(`Restored version ${v}`);
      setOpen(false);
    } catch (e) {
      toast.error(errMsg(e));
    }
  };

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger asChild>
        <Button variant="outline" size="sm" className="bg-[#FFFDF9]" disabled={!versions.length} data-testid={`${stage}-version-history-toggle`}>
          <History className="h-4 w-4 mr-1.5" /> Versions ({versions.length})
        </Button>
      </SheetTrigger>
      <SheetContent side="right" className="w-full sm:max-w-3xl bg-[#FAF7F2] overflow-y-auto" data-testid={`${stage}-version-sheet`}>
        <SheetHeader>
          <SheetTitle className="f-serif text-2xl capitalize">{stage} versions</SheetTitle>
        </SheetHeader>
        <div className="grid grid-cols-1 md:grid-cols-[220px_1fr] gap-5 mt-6">
          <ul className="space-y-2">
            {versions.map((v) => (
              <li key={v.version}>
                <button onClick={() => setSelected(v.version)} data-testid={`${stage}-version-${v.version}`}
                  className={`w-full text-left p-3 rounded-md border transition-colors ${
                    shown?.version === v.version ? "border-[#B45309] bg-[#FFFDF9]" : "border-[#E7E0D6] hover:bg-[#F4EFE6]"}`}>
                  <div className="text-sm font-semibold">v{v.version} · {SOURCE[v.source] || v.source}</div>
                  <div className="f-mono text-[11px] text-stone-500">{new Date(v.created_at).toLocaleString()} · {v.created_by}</div>
                  {v.notes && <div className="text-xs text-stone-600 mt-1 line-clamp-2 italic">"{v.notes}"</div>}
                </button>
              </li>
            ))}
          </ul>
          {shown && (
            <div className="card-warm p-5 space-y-4">
              <div className="flex items-center justify-between gap-2">
                <span className="f-mono text-xs text-stone-500">{shown.provider || "manual"}</span>
                {editable && (
                  <Button size="sm" onClick={() => restore(shown.version)} data-testid={`${stage}-restore-version-btn`}>
                    <RotateCcw className="h-4 w-4 mr-1.5" /> Restore v{shown.version}
                  </Button>
                )}
              </div>
              <Markdown text={shown.content} />
            </div>
          )}
        </div>
      </SheetContent>
    </Sheet>
  );
}
