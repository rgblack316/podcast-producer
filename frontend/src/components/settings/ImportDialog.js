import { useEffect, useState } from "react";
import { Loader2, Sparkles } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { api, errMsg } from "@/lib/api";

const EMPTY = { title: "", episode_number: "", topic: "", primary_scripture: "", supporting_text: "", themes_text: "" };

export function ImportDialog({ doc, onClose, onDone }) {
  const [f, setF] = useState(EMPTY);
  const [busy, setBusy] = useState(null);
  useEffect(() => { if (doc) setF({ ...EMPTY, title: doc.filename.replace(/\.docx$/i, "") }); }, [doc]);
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });

  const suggest = async () => {
    setBusy("suggest");
    try {
      const { data } = await api.post(`/documents/${doc.id}/suggest-metadata`, {});
      setF({ ...data, supporting_text: data.supporting_scriptures.join("\n"), themes_text: data.themes.join(", ") });
      toast.success("Suggestions filled in. Review before saving.");
    } catch (e) {
      toast.error(errMsg(e));
    } finally {
      setBusy(null);
    }
  };

  const save = async () => {
    setBusy("save");
    try {
      await api.post(`/documents/${doc.id}/import`, {
        title: f.title, episode_number: f.episode_number, topic: f.topic, primary_scripture: f.primary_scripture,
        supporting_scriptures: f.supporting_text.split(/\n|;/).map((s) => s.trim()).filter(Boolean),
        themes: f.themes_text.split(",").map((s) => s.trim()).filter(Boolean),
      });
      toast.success("Added to the episode library as Published");
      onDone();
      onClose();
    } catch (e) {
      toast.error(errMsg(e));
    } finally {
      setBusy(null);
    }
  };

  const valid = f.title.trim() && f.topic.trim() && f.primary_scripture.trim();
  return (
    <Dialog open={!!doc} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-2xl bg-[#FAF7F2]" data-testid="import-dialog">
        <DialogHeader><DialogTitle className="f-serif text-2xl">Add to library</DialogTitle></DialogHeader>
        <Button variant="outline" className="bg-[#FFFDF9] w-fit" onClick={suggest} disabled={!!busy} data-testid="import-suggest-btn">
          {busy === "suggest" ? <Loader2 className="h-4 w-4 mr-1.5 animate-spin" /> : <Sparkles className="h-4 w-4 mr-1.5" />} Suggest details with AI
        </Button>
        <div className="grid grid-cols-1 sm:grid-cols-6 gap-4">
          <div className="sm:col-span-4 space-y-1.5"><Label>Title *</Label><Input value={f.title} onChange={set("title")} className="bg-[#FFFDF9]" data-testid="import-title-input" /></div>
          <div className="sm:col-span-2 space-y-1.5"><Label>Episode #</Label><Input value={f.episode_number} onChange={set("episode_number")} className="bg-[#FFFDF9]" data-testid="import-number-input" /></div>
          <div className="sm:col-span-6 space-y-1.5"><Label>Topic *</Label><Input value={f.topic} onChange={set("topic")} className="bg-[#FFFDF9]" data-testid="import-topic-input" /></div>
          <div className="sm:col-span-3 space-y-1.5"><Label>Primary scripture *</Label><Input value={f.primary_scripture} onChange={set("primary_scripture")} className="bg-[#FFFDF9] f-serif" data-testid="import-scripture-input" /></div>
          <div className="sm:col-span-3 space-y-1.5"><Label>Themes</Label><Input value={f.themes_text} onChange={set("themes_text")} className="bg-[#FFFDF9]" data-testid="import-themes-input" /></div>
          <div className="sm:col-span-6 space-y-1.5"><Label>Supporting scriptures (one per line)</Label><Textarea rows={2} value={f.supporting_text} onChange={set("supporting_text")} className="bg-[#FFFDF9] f-serif" data-testid="import-supporting-input" /></div>
        </div>
        <DialogFooter>
          <Button onClick={save} disabled={!valid || !!busy} data-testid="import-save-btn">
            {busy === "save" && <Loader2 className="h-4 w-4 mr-1.5 animate-spin" />} Add as published episode
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
