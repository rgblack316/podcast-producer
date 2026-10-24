import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { api, errMsg } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";

export const COLORS = ["#B45309", "#3F6212", "#0369A1", "#6B21A8", "#BE123C", "#0F766E", "#A16207", "#44403C"];

export function SeriesDialog({ series, open, onClose, onSaved }) {
  const { user } = useAuth();
  const [f, setF] = useState({ name: "", description: "", color: COLORS[0] });
  useEffect(() => { if (open) setF(series ? { name: series.name, description: series.description, color: series.color } : { name: "", description: "", color: COLORS[0] }); }, [open, series]);
  const save = async () => {
    try {
      if (series) await api.put(`/series/${series.id}`, f); else await api.post("/series", f);
      toast.success(series ? "Series updated" : "Series created");
      onSaved();
      onClose();
    } catch (e) { toast.error(errMsg(e)); }
  };
  const remove = async () => {
    if (!window.confirm(`Delete series "${series.name}"? Planned episodes stay on the calendar.`)) return;
    await api.delete(`/series/${series.id}`);
    toast.success("Series deleted");
    onSaved("deleted");
    onClose();
  };
  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="bg-[#FAF7F2]" data-testid="series-dialog">
        <DialogHeader><DialogTitle className="f-serif text-2xl">{series ? "Edit series" : "New series"}</DialogTitle></DialogHeader>
        <div className="space-y-4">
          <div className="space-y-1.5"><Label>Name</Label><Input value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} className="bg-[#FFFDF9]" data-testid="series-name-input" /></div>
          <div className="space-y-1.5"><Label>Description</Label><Textarea rows={2} value={f.description} onChange={(e) => setF({ ...f, description: e.target.value })} className="bg-[#FFFDF9]" data-testid="series-description-input" /></div>
          <div className="space-y-1.5"><Label>Color</Label>
            <div className="flex gap-2">
              {COLORS.map((c) => (
                <button key={c} onClick={() => setF({ ...f, color: c })} style={{ background: c }} data-testid={`series-color-${c.slice(1)}`}
                  className={`h-8 w-8 rounded-full border-2 transition-transform ${f.color === c ? "border-[#1C1917] scale-110" : "border-transparent"}`} />
              ))}
            </div>
          </div>
        </div>
        <DialogFooter className="gap-2 sm:justify-between">
          {series && user?.role === "admin" ? <Button variant="ghost" className="text-red-700" onClick={remove} data-testid="series-delete-btn">Delete</Button> : <span />}
          <Button onClick={save} disabled={!f.name.trim()} data-testid="series-save-btn">Save series</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
