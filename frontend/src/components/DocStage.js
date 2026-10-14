import { useEffect, useState } from "react";
import { Copy, Download, Loader2, PencilLine, Save, Sparkles, Wand2, X } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { api, downloadFile, errMsg } from "@/lib/api";
import { Markdown } from "@/components/Markdown";
import { VersionHistory } from "@/components/VersionHistory";
import { StageActions } from "@/components/StageActions";

export function Generating({ stage }) {
  return (
    <div className="py-20 flex flex-col items-center text-center gap-4" data-testid={`${stage}-generating`}>
      <div className="flex gap-1.5">
        {[0, 1, 2].map((i) => <span key={i} className="ink-dot h-2.5 w-2.5 rounded-full bg-[#B45309]" style={{ animationDelay: `${i * 0.2}s` }} />)}
      </div>
      <p className="f-serif text-xl italic text-[#44403C]">Writing the {stage}…</p>
      <p className="text-sm text-stone-500 max-w-sm">This usually takes 30 seconds to a few minutes. You can leave this page; the result will be saved.</p>
    </div>
  );
}

export function DocStage({ episode, stage, editable, providers, onChange }) {
  const content = episode[stage] || "";
  const generating = episode.generating?.stage === stage;
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(content);
  const [notes, setNotes] = useState("");
  const [provider, setProvider] = useState(providers.default_provider);
  const [busy, setBusy] = useState(false);

  useEffect(() => { if (!editing) setDraft(content); }, [content, editing]);
  useEffect(() => { setProvider(providers.default_provider); }, [providers.default_provider]);

  const generate = async (withNotes) => {
    setBusy(true);
    try {
      const { data } = await api.post(`/episodes/${episode.id}/${stage}/generate`, { provider, notes: withNotes ? notes : "" });
      onChange(data);
      if (withNotes) setNotes("");
    } catch (e) {
      toast.error(errMsg(e));
    } finally {
      setBusy(false);
    }
  };

  const save = async () => {
    setBusy(true);
    try {
      const { data } = await api.put(`/episodes/${episode.id}/${stage}`, { content: draft });
      onChange(data);
      setEditing(false);
      toast.success(`${stage === "outline" ? "Outline" : "Script"} saved as a new version`);
    } catch (e) {
      toast.error(errMsg(e));
    } finally {
      setBusy(false);
    }
  };

  const copy = async () => {
    await navigator.clipboard.writeText(content);
    toast.success("Copied to clipboard");
  };

  const exportDocx = () =>
    downloadFile(`/episodes/${episode.id}/export/${stage}.docx`, `${episode.title}-${stage}.docx`)
      .then(() => toast.success("Download started")).catch((e) => toast.error(errMsg(e)));

  const anyGenerating = !!episode.generating;
  const providerOptions = [["gemini", "Google Gemini", providers.gemini_configured], ["openai", "OpenAI ChatGPT", providers.openai_configured]];

  return (
    <div className="space-y-5" data-testid={`${stage}-workspace`}>
      <div className="flex flex-wrap items-center gap-2">
        {editable && (
          <Select value={provider} onValueChange={setProvider}>
            <SelectTrigger className="w-[210px] h-9 bg-[#FFFDF9]" data-testid={`${stage}-provider-select`}><SelectValue /></SelectTrigger>
            <SelectContent>
              {providerOptions.map(([v, label, ok]) => (
                <SelectItem key={v} value={v} disabled={!ok}>{label}{ok ? "" : " (no key)"}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}
        {editable && !editing && content && (
          <Button variant="outline" size="sm" className="bg-[#FFFDF9]" onClick={() => setEditing(true)} disabled={anyGenerating} data-testid={`${stage}-edit-btn`}>
            <PencilLine className="h-4 w-4 mr-1.5" /> Edit
          </Button>
        )}
        <VersionHistory episode={episode} stage={stage} editable={editable && !anyGenerating} onChange={onChange} />
        <div className="ml-auto flex gap-2">
          <Button variant="ghost" size="sm" onClick={copy} disabled={!content} data-testid={`${stage}-copy-btn`}>
            <Copy className="h-4 w-4 mr-1.5" /> Copy
          </Button>
          <Button variant="ghost" size="sm" onClick={exportDocx} disabled={!content} data-testid={`${stage}-export-docx-btn`}>
            <Download className="h-4 w-4 mr-1.5" /> .docx
          </Button>
        </div>
      </div>

      {episode.last_error && !anyGenerating && (
        <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-800 break-words" data-testid={`${stage}-error`}>
          Last generation failed: {episode.last_error}
        </div>
      )}

      <div className="min-h-[360px] rounded-lg border border-[#EFE8DC] bg-[#FFFDF9] p-5 sm:p-8" data-testid={`${stage}-editor-container`}>
        {generating ? <Generating stage={stage} /> : editing ? (
          <div className="space-y-3">
            <Textarea value={draft} onChange={(e) => setDraft(e.target.value)} rows={28}
              className="f-mono text-sm leading-relaxed bg-[#FFFDF9]" data-testid={`${stage}-editor-textarea`} />
            <div className="flex gap-2">
              <Button onClick={save} disabled={busy} data-testid={`${stage}-save-btn`}>
                {busy ? <Loader2 className="h-4 w-4 mr-1.5 animate-spin" /> : <Save className="h-4 w-4 mr-1.5" />} Save version
              </Button>
              <Button variant="ghost" onClick={() => { setEditing(false); setDraft(content); }} data-testid={`${stage}-cancel-edit-btn`}>
                <X className="h-4 w-4 mr-1.5" /> Cancel
              </Button>
            </div>
          </div>
        ) : content ? <Markdown text={content} testId={`${stage}-content`} /> : (
          <div className="py-16 text-center space-y-4" data-testid={`${stage}-empty`}>
            <p className="f-serif text-2xl text-[#1C1917]">No {stage} yet</p>
            <p className="text-stone-500 max-w-md mx-auto text-sm">
              {stage === "outline" ? "Draft an outline from the intake, planning template and example episodes."
                : "Write the full script from the approved outline."}
            </p>
            {editable && (
              <div className="flex flex-wrap justify-center gap-2">
                <Button className="rounded-full" onClick={() => generate(false)} disabled={busy || anyGenerating} data-testid={`${stage}-generate-btn`}>
                  {busy ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Sparkles className="h-4 w-4 mr-2" />} Generate {stage}
                </Button>
                <Button variant="outline" className="rounded-full bg-[#FFFDF9]" onClick={() => setEditing(true)} disabled={anyGenerating} data-testid={`${stage}-write-manually-btn`}>
                  <PencilLine className="h-4 w-4 mr-2" /> Write it myself
                </Button>
              </div>
            )}
          </div>
        )}
      </div>

      {editable && content && !editing && (
        <div className="rounded-lg bg-[#F4EFE6]/70 border border-[#E2DACD] p-4 space-y-3">
          <p className="eyebrow">Revise with AI</p>
          <Textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={3} className="bg-[#FFFDF9]"
            placeholder={stage === "outline" ? "e.g. Make the intro shorter and add a second application point" : "e.g. Warmer pastoral tone in the closing, tighten the exegesis"}
            data-testid={`${stage}-ai-prompt-input`} />
          <div className="flex flex-wrap gap-2">
            <Button onClick={() => generate(true)} disabled={!notes.trim() || busy || anyGenerating} data-testid={`${stage}-revise-btn`}>
              <Wand2 className="h-4 w-4 mr-1.5" /> Revise
            </Button>
            <Button variant="outline" className="bg-[#FFFDF9]" onClick={() => generate(false)} disabled={busy || anyGenerating} data-testid={`${stage}-regenerate-btn`}>
              <Sparkles className="h-4 w-4 mr-1.5" /> Regenerate from scratch
            </Button>
          </div>
        </div>
      )}

      <StageActions episode={episode} stage={stage} disabled={anyGenerating || editing} onChange={onChange} />
    </div>
  );
}
