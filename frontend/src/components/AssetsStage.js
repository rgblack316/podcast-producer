import { useEffect, useState } from "react";
import { Copy, Loader2, PencilLine, Save, Sparkles, Wand2, X } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { api, errMsg, fmtDate } from "@/lib/api";
import { Markdown } from "@/components/Markdown";
import { Generating } from "@/components/DocStage";
import { FeedSyncButton } from "@/components/FeedSyncButton";

const FIELDS = [
  ["description", "Episode description", false],
  ["show_notes", "Show notes", true],
  ["social_posts", "Social posts", true],
];

function AssetBlock({ field, label, md, value, editing, onEdit }) {
  const copy = async () => { await navigator.clipboard.writeText(value || ""); toast.success(`${label} copied`); };
  return (
    <div className="rounded-lg border border-[#EFE8DC] bg-[#FFFDF9] p-5 sm:p-6 space-y-3" data-testid={`assets-block-${field}`}>
      <div className="flex items-center justify-between">
        <p className="eyebrow">{label}</p>
        {!editing && <Button variant="ghost" size="sm" onClick={copy} disabled={!value} data-testid={`assets-copy-${field}`}><Copy className="h-4 w-4 mr-1.5" /> Copy</Button>}
      </div>
      {editing ? (
        <Textarea value={value} onChange={(e) => onEdit(e.target.value)} rows={md ? 14 : 4} className="f-mono text-sm bg-[#FFFDF9]" data-testid={`assets-input-${field}`} />
      ) : md ? <Markdown text={value} /> : <p className="f-serif text-lg leading-relaxed text-[#292524]">{value}</p>}
    </div>
  );
}

export function AssetsStage({ episode, providers, onChange }) {
  const assets = episode.assets;
  const ready = ["script_complete", "published"].includes(episode.status);
  const generating = episode.generating?.stage === "assets";
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState({});
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => { if (!editing) setDraft(assets || {}); }, [assets, editing]);

  const generate = async (withNotes) => {
    setBusy(true);
    try {
      const { data } = await api.post(`/episodes/${episode.id}/assets/generate`, { provider: providers.default_provider, notes: withNotes ? notes : "" });
      onChange(data);
      if (withNotes) setNotes("");
    } catch (e) { toast.error(errMsg(e)); } finally { setBusy(false); }
  };
  const save = async () => {
    try {
      const { data } = await api.put(`/episodes/${episode.id}/assets`, {
        show_notes: draft.show_notes || "", description: draft.description || "", social_posts: draft.social_posts || "" });
      onChange(data);
      setEditing(false);
      toast.success("Show notes saved");
    } catch (e) { toast.error(errMsg(e)); }
  };

  if (!ready) {
    return <p className="py-16 text-center text-stone-500 italic" data-testid="assets-locked">Mark the script complete to create show notes, a description and social posts.</p>;
  }
  if (generating) return <Generating stage="show notes" />;
  return (
    <div className="space-y-5" data-testid="assets-workspace">
      {episode.last_error && !episode.generating && (
        <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-800 break-words" data-testid="assets-error">Last generation failed: {episode.last_error}</div>
      )}
      {!assets ? (
        <div className="py-16 text-center space-y-4 rounded-lg border border-[#EFE8DC] bg-[#FFFDF9]" data-testid="assets-empty">
          <p className="f-serif text-2xl">Publishing kit</p>
          <p className="text-stone-500 text-sm max-w-md mx-auto">One click turns the finished script into show notes, an episode description and ready-to-post social captions.</p>
          <Button className="rounded-full" onClick={() => generate(false)} disabled={busy || !!episode.generating} data-testid="assets-generate-btn">
            {busy ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Sparkles className="h-4 w-4 mr-2" />} Create show notes & posts
          </Button>
          <div><FeedSyncButton episode={episode} what="show_notes" onChange={onChange} /></div>
        </div>
      ) : (
        <>
          <div className="flex flex-wrap items-center gap-2">
            {editing ? (
              <>
                <Button size="sm" onClick={save} data-testid="assets-save-btn"><Save className="h-4 w-4 mr-1.5" /> Save</Button>
                <Button size="sm" variant="ghost" onClick={() => setEditing(false)} data-testid="assets-cancel-btn"><X className="h-4 w-4 mr-1.5" /> Cancel</Button>
              </>
            ) : (
              <Button size="sm" variant="outline" className="bg-[#FFFDF9]" onClick={() => setEditing(true)} data-testid="assets-edit-btn"><PencilLine className="h-4 w-4 mr-1.5" /> Edit</Button>
            )}
            <span className="ml-auto f-mono text-[11px] text-stone-500">{assets.source === "rss" ? "From RSS feed · " : ""}Updated {fmtDate(assets.updated_at)} · {assets.updated_by}</span>
            {!editing && <FeedSyncButton episode={episode} what="show_notes" onChange={onChange} />}
          </div>
          {FIELDS.map(([f, label, md]) => (
            <AssetBlock key={f} field={f} label={label} md={md} value={(editing ? draft : assets)[f] || ""} editing={editing}
              onEdit={(v) => setDraft({ ...draft, [f]: v })} />
          ))}
          {!editing && (
            <div className="rounded-lg bg-[#F4EFE6]/70 border border-[#E2DACD] p-4 space-y-3">
              <p className="eyebrow">Revise with AI</p>
              <Textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={2} className="bg-[#FFFDF9]"
                placeholder="e.g. Shorter Instagram caption, add a call to subscribe" data-testid="assets-ai-prompt-input" />
              <div className="flex gap-2">
                <Button onClick={() => generate(true)} disabled={!notes.trim() || busy || !!episode.generating} data-testid="assets-revise-btn"><Wand2 className="h-4 w-4 mr-1.5" /> Revise</Button>
                <Button variant="outline" className="bg-[#FFFDF9]" onClick={() => generate(false)} disabled={busy || !!episode.generating} data-testid="assets-regenerate-btn"><Sparkles className="h-4 w-4 mr-1.5" /> Regenerate</Button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
