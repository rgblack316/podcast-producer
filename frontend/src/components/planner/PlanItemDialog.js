import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ExternalLink, Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { api, errMsg } from "@/lib/api";
import { StatusBadge } from "@/components/StatusBadge";

const NONE = "__none";

export function SeriesSelect({ series, value, onChange, testId }) {
  return (
    <Select value={value || NONE} onValueChange={(v) => onChange(v === NONE ? null : v)}>
      <SelectTrigger className="bg-[#FFFDF9]" data-testid={testId}><SelectValue /></SelectTrigger>
      <SelectContent>
        <SelectItem value={NONE}>No series</SelectItem>
        {series.map((s) => (
          <SelectItem key={s.id} value={s.id}><span className="inline-block h-2.5 w-2.5 rounded-full mr-2" style={{ background: s.color }} />{s.name}</SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}

// item: existing plan item, or a draft {title, topic, ...} to create
export function PlanItemDialog({ item, series, onClose, onSaved }) {
  const navigate = useNavigate();
  const [f, setF] = useState({});
  useEffect(() => { if (item) setF({ title: item.title || item.episode?.title || "", date: item.date || "", series_id: item.series_id || null, notes: item.notes || "" }); }, [item]);
  if (!item) return null;
  const isNew = !item.id;

  const save = async () => {
    try {
      if (isNew) await api.post("/plan", { ...item, ...f, date: f.date || null });
      else await api.patch(`/plan/${item.id}`, { ...f, date: f.date || null });
      toast.success(isNew ? "Added to plan" : "Plan updated");
      onSaved();
      onClose();
    } catch (e) { toast.error(errMsg(e)); }
  };
  const remove = async () => {
    await api.delete(`/plan/${item.id}`);
    toast.success("Removed from plan");
    onSaved();
    onClose();
  };
  const startEpisode = () => navigate("/episodes/new", { state: { prefill: { ...item, title: f.title, target_date: f.date || "" }, plan_id: item.id } });

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="bg-[#FAF7F2]" data-testid="plan-item-dialog">
        <DialogHeader><DialogTitle className="f-serif text-2xl">{isNew ? "Add to plan" : "Planned episode"}</DialogTitle></DialogHeader>
        <div className="space-y-4">
          <div className="space-y-1.5"><Label>Title</Label>
            <Input value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} className="bg-[#FFFDF9]" disabled={!!item.episode_id} data-testid="plan-title-input" /></div>
          {(item.primary_scripture || item.episode?.primary_scripture) && (
            <p className="f-serif italic text-[#92400E]">{item.episode?.primary_scripture || item.primary_scripture} · <span className="not-italic text-stone-600 text-sm">{item.episode?.topic || item.topic}</span></p>
          )}
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5"><Label>Date</Label>
              <Input type="date" value={f.date} onChange={(e) => setF({ ...f, date: e.target.value })} className="bg-[#FFFDF9]" data-testid="plan-date-input" /></div>
            <div className="space-y-1.5"><Label>Series</Label>
              <SeriesSelect series={series} value={f.series_id} onChange={(v) => setF({ ...f, series_id: v })} testId="plan-series-select" /></div>
          </div>
          <div className="space-y-1.5"><Label>Notes</Label>
            <Textarea rows={2} value={f.notes} onChange={(e) => setF({ ...f, notes: e.target.value })} className="bg-[#FFFDF9]" data-testid="plan-notes-input" /></div>
          {item.episode && (
            <div className="flex items-center gap-2 text-sm"><StatusBadge status={item.episode.status} testId="plan-episode-status" /> Linked to an episode</div>
          )}
        </div>
        <DialogFooter className="gap-2 sm:justify-between">
          <div className="flex gap-2">
            {!isNew && <Button variant="ghost" className="text-red-700" onClick={remove} data-testid="plan-delete-btn"><Trash2 className="h-4 w-4 mr-1" /> Remove</Button>}
            {!isNew && (item.episode_id ? (
              <Button variant="outline" className="bg-[#FFFDF9]" onClick={() => navigate(`/episodes/${item.episode_id}`)} data-testid="plan-open-episode-btn"><ExternalLink className="h-4 w-4 mr-1" /> Open episode</Button>
            ) : (
              <Button variant="outline" className="bg-[#FFFDF9]" onClick={startEpisode} data-testid="plan-start-episode-btn"><Plus className="h-4 w-4 mr-1" /> Start episode</Button>
            ))}
          </div>
          <Button onClick={save} disabled={!f.title?.trim()} data-testid="plan-save-btn">{isNew ? "Add to plan" : "Save"}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
