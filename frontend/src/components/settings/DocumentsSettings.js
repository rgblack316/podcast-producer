import { useEffect, useRef, useState } from "react";
import { Eye, FileText, Import, Loader2, Trash2, Upload } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { api, errMsg, fmtDate } from "@/lib/api";
import { ImportDialog } from "@/components/settings/ImportDialog";

function UploadButton({ kind, multiple, onDone, label }) {
  const ref = useRef();
  const [busy, setBusy] = useState(false);
  const upload = async (files) => {
    setBusy(true);
    for (const f of files) {
      const fd = new FormData();
      fd.append("file", f);
      fd.append("kind", kind);
      try {
        await api.post("/documents/upload", fd);
        toast.success(`Uploaded ${f.name}`);
      } catch (e) {
        toast.error(`${f.name}: ${errMsg(e)}`);
      }
    }
    setBusy(false);
    ref.current.value = "";
    onDone();
  };
  return (
    <>
      <input ref={ref} type="file" accept=".docx,.pdf,.txt,.md,.markdown,.rtf,.odt,.html,.htm,.csv,.tsv,.rst,.text,.log,.json,.yaml,.yml,.xml" multiple={multiple} className="hidden" onChange={(e) => upload([...e.target.files])}
        data-testid={`settings-docx-upload-input-${kind}`} />
      <Button onClick={() => ref.current.click()} disabled={busy} className="rounded-full" data-testid={`upload-${kind}-btn`}>
        {busy ? <Loader2 className="h-4 w-4 mr-1.5 animate-spin" /> : <Upload className="h-4 w-4 mr-1.5" />} {label}
      </Button>
    </>
  );
}

function ViewDoc({ doc, onClose }) {
  const [full, setFull] = useState(null);
  useEffect(() => { if (doc) api.get(`/documents/${doc.id}`).then((r) => setFull(r.data)); else setFull(null); }, [doc]);
  return (
    <Dialog open={!!doc} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-3xl max-h-[85vh] overflow-y-auto bg-[#FAF7F2]">
        <DialogHeader><DialogTitle className="f-serif text-2xl">{doc?.filename}</DialogTitle></DialogHeader>
        <pre className="whitespace-pre-wrap f-serif text-base leading-relaxed text-[#292524]" data-testid="document-full-text">{full?.text || "Loading…"}</pre>
      </DialogContent>
    </Dialog>
  );
}

function DocRow({ d, onToggle, onDelete, onView, onImport }) {
  return (
    <li className="flex flex-col sm:flex-row sm:items-center gap-3 py-4" data-testid={`document-row-${d.id}`}>
      <FileText className="h-5 w-5 text-[#B45309] shrink-0 hidden sm:block" />
      <div className="min-w-0 flex-1">
        <div className="font-medium text-[#1C1917] truncate">{d.filename}</div>
        <div className="f-mono text-[11px] text-stone-500">{d.char_count.toLocaleString()} chars · {fmtDate(d.created_at)}
          {d.imported_episode_id && " · in library"}</div>
      </div>
      <div className="flex items-center gap-2">
        <label className="flex items-center gap-2 text-xs text-stone-600 mr-2">
          <Switch checked={d.active} onCheckedChange={(v) => onToggle(d, v)} data-testid={`document-active-toggle-${d.id}`} /> {d.active ? "Active" : "Off"}
        </label>
        <Button variant="ghost" size="icon" onClick={() => onView(d)} data-testid={`document-view-${d.id}`}><Eye className="h-4 w-4" /></Button>
        {onImport && !d.imported_episode_id && (
          <Button variant="outline" size="sm" className="bg-[#FFFDF9]" onClick={() => onImport(d)} data-testid={`document-import-${d.id}`}>
            <Import className="h-4 w-4 mr-1" /> Add to library
          </Button>
        )}
        <Button variant="ghost" size="icon" className="text-red-700" onClick={() => onDelete(d)} data-testid={`document-delete-${d.id}`}><Trash2 className="h-4 w-4" /></Button>
      </div>
    </li>
  );
}

export function DocumentsSettings() {
  const [docs, setDocs] = useState([]);
  const [viewing, setViewing] = useState(null);
  const [importing, setImporting] = useState(null);
  const load = () => api.get("/documents").then((r) => setDocs(r.data));
  useEffect(() => { load(); }, []);

  const toggle = async (d, active) => {
    try { await api.patch(`/documents/${d.id}`, { active }); load(); } catch (e) { toast.error(errMsg(e)); }
  };
  const remove = async (d) => {
    if (!window.confirm(`Delete ${d.filename}?`)) return;
    await api.delete(`/documents/${d.id}`);
    toast.success("Document deleted");
    load();
  };
  const templates = docs.filter((d) => d.kind === "template");
  const examples = docs.filter((d) => d.kind === "example");
  const rowProps = { onToggle: toggle, onDelete: remove, onView: setViewing };

  return (
    <div className="space-y-6" data-testid="settings-documents">
      <section className="card-warm p-6">
        <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
          <div>
            <h3 className="f-serif text-2xl">Planning template</h3>
            <p className="text-sm text-stone-500 mt-1 max-w-xl">The structure every outline and script follows. Only one template is active at a time; uploading a new one replaces it.</p>
          </div>
          <UploadButton kind="template" label="Upload template" onDone={load} />
        </div>
        <ul className="divide-y divide-[#EFE8DC] mt-4" data-testid="template-list">
          {templates.length ? templates.map((d) => <DocRow key={d.id} d={d} {...rowProps} />) : <p className="text-sm text-stone-500 italic py-3">No template uploaded yet.</p>}
        </ul>
      </section>
      <section className="card-warm p-6">
        <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
          <div>
            <h3 className="f-serif text-2xl">Example episodes</h3>
            <p className="text-sm text-stone-500 mt-1 max-w-xl">Past scripts used for tone and format. Turn individual examples on or off, and add them to the library to track what's been covered.</p>
          </div>
          <UploadButton kind="example" multiple label="Upload examples" onDone={load} />
        </div>
        <ul className="divide-y divide-[#EFE8DC] mt-4" data-testid="example-list">
          {examples.length ? examples.map((d) => <DocRow key={d.id} d={d} {...rowProps} onImport={setImporting} />) : <p className="text-sm text-stone-500 italic py-3">No examples uploaded yet.</p>}
        </ul>
      </section>
      <ViewDoc doc={viewing} onClose={() => setViewing(null)} />
      <ImportDialog doc={importing} onClose={() => setImporting(null)} onDone={load} />
    </div>
  );
}
