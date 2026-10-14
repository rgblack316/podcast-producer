import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { api, errMsg } from "@/lib/api";

const toForm = (it, full) => {
  const s = it?.suggestion || {};
  return {
    title: s.title || it?.title || "", episode_number: s.episode_number || it?.episode_number || "", topic: s.topic || "",
    primary_scripture: s.primary_scripture || "", supporting_text: (s.supporting_scriptures || []).join("\n"),
    themes_text: (s.themes || []).join(", "), content: full?.content || full?.description || "",
  };
};

export function RssItemDialog({ item, onClose, onSaved }) {
  const [f, setF] = useState(toForm(null));
  useEffect(() => {
    if (!item) return;
    setF(toForm(item));
    api.get(`/rss/items/${item.id}`).then((r) => setF(toForm(r.data, r.data)));
  }, [item]);
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });

  const save = async (andImport) => {
    try {
      await api.put(`/rss/items/${item.id}/suggestion`, {
        title: f.title, episode_number: f.episode_number, topic: f.topic, primary_scripture: f.primary_scripture,
        supporting_scriptures: f.supporting_text.split(/\n|;/).map((s) => s.trim()).filter(Boolean),
        themes: f.themes_text.split(",").map((s) => s.trim()).filter(Boolean),
      });
      if (andImport) {
        const { data } = await api.post("/rss/items/import", { ids: [item.id] });
        if (!data.imported) throw new Error("Topic and primary scripture are required to import");
        toast.success("Added to library");
      } else toast.success("Saved");
      onSaved();
      onClose();
    } catch (e) {
      toast.error(errMsg(e));
    }
  };
  const field = (k, label, props = {}) => (
    <div className={`space-y-1.5 ${props.span || "sm:col-span-3"}`}>
      <Label>{label}</Label>
      {props.area ? <Textarea rows={2} value={f[k]} onChange={set(k)} className="bg-[#FFFDF9]" data-testid={`rss-dialog-${k}`} />
        : <Input value={f[k]} onChange={set(k)} className="bg-[#FFFDF9]" data-testid={`rss-dialog-${k}`} />}
    </div>
  );
  return (
    <Dialog open={!!item} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto bg-[#FAF7F2]" data-testid="rss-item-dialog">
        <DialogHeader><DialogTitle className="f-serif text-2xl">{item?.title}</DialogTitle></DialogHeader>
        <div className="grid grid-cols-1 sm:grid-cols-6 gap-4">
          {field("title", "Title *", { span: "sm:col-span-4" })}
          {field("episode_number", "Episode #", { span: "sm:col-span-2" })}
          {field("topic", "Topic *", { span: "sm:col-span-6" })}
          {field("primary_scripture", "Primary scripture *")}
          {field("themes_text", "Themes (comma separated)")}
          {field("supporting_text", "Supporting scriptures (one per line)", { span: "sm:col-span-6", area: true })}
        </div>
        <div className="space-y-1.5">
          <p className="eyebrow">Source text</p>
          <div className="max-h-56 overflow-y-auto rounded-md border border-[#E7E0D6] bg-[#FFFDF9] p-3 text-sm whitespace-pre-wrap text-stone-700" data-testid="rss-dialog-content">
            {f.content || "No text available."}
          </div>
        </div>
        <DialogFooter className="gap-2">
          <Button variant="outline" className="bg-[#FFFDF9]" onClick={() => save(false)} data-testid="rss-dialog-save-btn">Save</Button>
          <Button onClick={() => save(true)} disabled={!f.topic.trim() || !f.primary_scripture.trim()} data-testid="rss-dialog-import-btn">Save & add to library</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
