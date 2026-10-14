import { useEffect, useState } from "react";
import { Layers, Plus } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api, errMsg } from "@/lib/api";
import { SeriesSelect } from "@/components/planner/PlanItemDialog";
import { COLORS } from "@/components/planner/SeriesDialog";

export function AddToSeriesDialog({ open, episodeIds, series, onClose, onDone }) {
  const [seriesId, setSeriesId] = useState(null);
  const [newName, setNewName] = useState("");
  const [color, setColor] = useState(COLORS[0]);
  const [busy, setBusy] = useState(false);
  useEffect(() => { if (open) { setSeriesId(series[0]?.id || null); setNewName(""); } }, [open, series]);

  const save = async () => {
    setBusy(true);
    try {
      let id = seriesId;
      if (!id) id = (await api.post("/series", { name: newName.trim(), description: "", color })).data.id;
      const { data } = await api.post(`/series/${id}/episodes`, { episode_ids: episodeIds });
      toast.success(`Added ${data.added} episode${data.added === 1 ? "" : "s"} to the series`);
      onDone();
      onClose();
    } catch (e) { toast.error(errMsg(e)); } finally { setBusy(false); }
  };

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="bg-[#FAF7F2]" data-testid="add-to-series-dialog">
        <DialogHeader><DialogTitle className="f-serif text-2xl flex items-center gap-2"><Layers className="h-5 w-5 text-[#B45309]" /> Add {episodeIds.length} to a series</DialogTitle></DialogHeader>
        <div className="space-y-4">
          <div className="space-y-1.5">
            <Label>Series</Label>
            <SeriesSelect series={series} value={seriesId} onChange={setSeriesId} testId="add-to-series-select" />
            <p className="text-xs text-stone-500">Choose "No series" to create a new one below. Episodes already in another series are moved.</p>
          </div>
          {!seriesId && (
            <div className="space-y-2 rounded-lg border border-[#E7E0D6] bg-[#FFFDF9] p-3" data-testid="add-to-series-new">
              <Label className="flex items-center gap-1"><Plus className="h-3.5 w-3.5" /> New series name</Label>
              <Input value={newName} onChange={(e) => setNewName(e.target.value)} className="bg-[#FFFDF9]" placeholder="e.g. Psalms of Ascent" data-testid="add-to-series-new-name" />
              <div className="flex gap-2">
                {COLORS.map((c) => (
                  <button key={c} onClick={() => setColor(c)} style={{ background: c }} data-testid={`add-to-series-color-${c.slice(1)}`}
                    className={`h-7 w-7 rounded-full border-2 ${color === c ? "border-[#1C1917] scale-110" : "border-transparent"}`} />
                ))}
              </div>
            </div>
          )}
        </div>
        <DialogFooter>
          <Button onClick={save} disabled={busy || (!seriesId && !newName.trim())} data-testid="add-to-series-save-btn">Add to series</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
