import { useEffect, useRef, useState } from "react";
import { Check, Download, ImagePlus, Loader2, MessageCircle, Send, Star, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { API, api, errMsg } from "@/lib/api";
import { Generating } from "@/components/DocStage";

const imgUrl = (ep, img) => `${API}/episodes/${ep.id}/artwork/${img.id}.png`;

function Chat({ episode, art, onChange, providers }) {
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const end = useRef();
  useEffect(() => { end.current?.scrollIntoView({ block: "nearest" }); }, [art.messages.length]);

  const send = async () => {
    setBusy(true);
    try {
      const { data } = await api.post(`/episodes/${episode.id}/artwork/brainstorm`, { notes: note, provider: providers.default_provider });
      onChange(data);
      setNote("");
    } catch (e) { toast.error(errMsg(e)); } finally { setBusy(false); }
  };
  return (
    <div className="rounded-lg border border-[#EFE8DC] bg-[#FFFDF9] p-4 space-y-3" data-testid="artwork-chat">
      <p className="eyebrow flex items-center gap-1.5"><MessageCircle className="h-3.5 w-3.5" /> Brainstorm with the art director</p>
      <div className="max-h-64 overflow-y-auto space-y-2 pr-1">
        {art.messages.length === 0 && <p className="text-sm text-stone-500 italic">Start with your own idea, or just ask for concepts. The AI uses the title, topic, themes and scripture.</p>}
        {art.messages.map((m, i) => (
          <div key={i} className={`text-sm rounded-lg px-3 py-2 max-w-[85%] ${m.role === "producer" ? "ml-auto bg-[#B45309] text-white" : "bg-[#F4EFE6] text-[#292524]"}`}
            data-testid={`artwork-message-${i}`}>{m.content}</div>
        ))}
        <div ref={end} />
      </div>
      <div className="flex gap-2">
        <Textarea value={note} onChange={(e) => setNote(e.target.value)} rows={2} className="bg-[#FFFDF9]"
          placeholder={art.messages.length ? "e.g. More minimal, warmer light, try a watercolor version of #2" : "e.g. Something with a desert well at dusk"}
          data-testid="artwork-brainstorm-input" />
        <Button onClick={send} disabled={busy} className="self-end" data-testid="artwork-brainstorm-btn">
          {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
          <span className="ml-1.5">{art.messages.length ? "Send" : "Get ideas"}</span>
        </Button>
      </div>
    </div>
  );
}

function Concepts({ art, picked, onPick }) {
  const latest = [...art.concepts].reverse();
  if (!latest.length) return null;
  return (
    <div className="space-y-2">
      <p className="eyebrow">Concepts ({latest.length})</p>
      <div className="grid sm:grid-cols-2 gap-3 max-h-[420px] overflow-y-auto pr-1">
        {latest.map((c) => (
          <button key={c.id} onClick={() => onPick(c)} data-testid={`artwork-concept-${c.id}`}
            className={`text-left rounded-lg border p-4 transition-colors ${picked === c.id ? "border-[#B45309] bg-[#FEF3C7]/50" : "border-[#E7E0D6] bg-[#FFFDF9] hover:bg-[#F4EFE6]"}`}>
            <div className="flex items-start justify-between gap-2">
              <span className="f-serif text-lg text-[#1C1917]">{c.title}</span>
              {picked === c.id && <Check className="h-4 w-4 text-[#B45309] shrink-0" />}
            </div>
            <p className="text-sm text-stone-600 mt-1">{c.description}</p>
          </button>
        ))}
      </div>
    </div>
  );
}

function Gallery({ episode, art, onChange }) {
  const act = async (fn, msg) => { try { onChange((await fn()).data); toast.success(msg); } catch (e) { toast.error(errMsg(e)); } };
  if (!art.images.length) return null;
  return (
    <div className="space-y-2">
      <p className="eyebrow">Artwork ({art.images.length})</p>
      <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
        {[...art.images].reverse().map((img) => {
          const selected = art.selected_image_id === img.id;
          return (
            <div key={img.id} className={`group relative rounded-lg overflow-hidden border-2 ${selected ? "border-[#B45309]" : "border-transparent"}`} data-testid={`artwork-image-${img.id}`}>
              <img src={imgUrl(episode, img)} alt={img.prompt} title={img.prompt} className="w-full aspect-square object-cover bg-[#F4EFE6]" />
              {selected && <span className="absolute top-2 left-2 bg-[#B45309] text-white text-[11px] font-semibold px-2 py-0.5 rounded-full">Episode art</span>}
              <div className="absolute inset-x-0 bottom-0 p-2 flex gap-1 justify-end bg-gradient-to-t from-black/60 to-transparent opacity-100 md:opacity-0 group-hover:opacity-100 transition-opacity">
                {!selected && (
                  <Button size="icon" variant="secondary" className="h-8 w-8" title="Use as episode art" data-testid={`artwork-select-${img.id}`}
                    onClick={() => act(() => api.post(`/episodes/${episode.id}/artwork/${img.id}/select`), "Set as episode art")}><Star className="h-4 w-4" /></Button>
                )}
                <a href={imgUrl(episode, img)} download={`${episode.title}-art.png`} data-testid={`artwork-download-${img.id}`}>
                  <Button size="icon" variant="secondary" className="h-8 w-8" title="Download"><Download className="h-4 w-4" /></Button>
                </a>
                <Button size="icon" variant="secondary" className="h-8 w-8 text-red-700" title="Delete" data-testid={`artwork-delete-${img.id}`}
                  onClick={() => window.confirm("Delete this image?") && act(() => api.delete(`/episodes/${episode.id}/artwork/${img.id}`), "Image deleted")}><Trash2 className="h-4 w-4" /></Button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function ArtworkStudio({ episode, providers, onChange }) {
  const art = { messages: [], concepts: [], images: [], selected_image_id: null, ...(episode.artwork || {}) };
  const [picked, setPicked] = useState(null);
  const [prompt, setPrompt] = useState("");
  const [busy, setBusy] = useState(false);
  const imageProvider = providers.image_provider || "gemini";

  const pick = (c) => { setPicked(c.id); setPrompt(c.prompt); };
  const generate = async () => {
    setBusy(true);
    try {
      const { data } = await api.post(`/episodes/${episode.id}/artwork/generate`, { prompt, provider: imageProvider, concept_id: picked });
      onChange(data);
    } catch (e) { toast.error(errMsg(e)); } finally { setBusy(false); }
  };

  return (
    <div className="space-y-5" data-testid="artwork-studio">
      <Chat episode={episode} art={art} onChange={onChange} providers={providers} />
      <Concepts art={art} picked={picked} onPick={pick} />
      <div className="rounded-lg bg-[#F4EFE6]/70 border border-[#E2DACD] p-4 space-y-3">
        <p className="eyebrow">Final image prompt · square 1:1</p>
        <Textarea value={prompt} onChange={(e) => setPrompt(e.target.value)} rows={5} className="bg-[#FFFDF9]"
          placeholder="Pick a concept above to load its prompt, or write your own." data-testid="artwork-prompt-input" />
        <div className="flex flex-wrap items-center gap-3">
          <Button className="rounded-full" onClick={generate} disabled={!prompt.trim() || busy || !!episode.art_generating} data-testid="artwork-generate-btn">
            {busy || episode.art_generating ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <ImagePlus className="h-4 w-4 mr-2" />} Generate artwork
          </Button>
          <span className="f-mono text-xs text-stone-500" data-testid="artwork-provider-label">
            {imageProvider === "gemini" ? `Gemini · ${providers.gemini_image_model}` : `OpenAI · ${providers.openai_image_model}`}
          </span>
        </div>
      </div>
      {episode.art_error && !episode.art_generating && (
        <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-800 break-words" data-testid="artwork-error">Last image failed: {episode.art_error}</div>
      )}
      {episode.art_generating && <Generating stage="artwork" />}
      <Gallery episode={episode} art={art} onChange={onChange} />
    </div>
  );
}
