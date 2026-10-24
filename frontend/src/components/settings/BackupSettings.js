import { useRef, useState } from "react";
import { DatabaseBackup, Loader2, Upload } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter,
  AlertDialogHeader, AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { api, downloadFile, errMsg } from "@/lib/api";

export function BackupButton({ className = "" }) {
  const [busy, setBusy] = useState(false);
  const run = async () => {
    setBusy(true);
    try {
      await downloadFile("/backup", `bible-bytes-backup-${new Date().toISOString().slice(0, 10)}.zip`);
      toast.success("Backup downloaded. Store it somewhere safe; it contains account data (AI keys are not included).");
    } catch (e) { toast.error(errMsg(e)); } finally { setBusy(false); }
  };
  return (
    <Button variant="outline" className={`rounded-full bg-[#FFFDF9] ${className}`} onClick={run} disabled={busy} data-testid="backup-download-btn">
      {busy ? <Loader2 className="h-4 w-4 mr-1.5 animate-spin" /> : <DatabaseBackup className="h-4 w-4 mr-1.5" />} Back up now
    </Button>
  );
}

export function BackupSettings() {
  const ref = useRef();
  const [file, setFile] = useState(null);
  const [busy, setBusy] = useState(false);
  const restore = async () => {
    setBusy(true);
    const fd = new FormData();
    fd.append("file", file);
    try {
      await api.post("/backup/restore", fd);
      toast.success("Backup restored. Please sign in again.");
      setTimeout(() => (window.location.href = "/login"), 800);
    } catch (e) { toast.error(errMsg(e)); setBusy(false); setFile(null); }
  };
  return (
    <div className="space-y-6" data-testid="settings-backup">
      <div className="card-warm p-6 space-y-3">
        <h3 className="f-serif text-2xl">Download a backup</h3>
        <p className="text-sm text-stone-500 max-w-2xl">One .zip with every episode, version, document, user account, plan, setting (including API keys) and generated artwork. Keep it private.</p>
        <BackupButton />
      </div>
      <div className="card-warm p-6 space-y-3">
        <h3 className="f-serif text-2xl">Restore from a backup</h3>
        <p className="text-sm text-stone-500 max-w-2xl">Replaces <strong>everything</strong> in this installation with the backup's contents, including user accounts. You'll be signed out.</p>
        <input ref={ref} type="file" accept=".zip" className="hidden" onChange={(e) => { setFile(e.target.files[0] || null); e.target.value = ""; }} data-testid="restore-file-input" />
        <Button variant="outline" className="rounded-full bg-[#FFFDF9]" onClick={() => ref.current.click()} data-testid="restore-choose-btn">
          <Upload className="h-4 w-4 mr-1.5" /> Choose backup file…
        </Button>
      </div>
      <AlertDialog open={!!file} onOpenChange={(o) => !o && setFile(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Restore {file?.name}?</AlertDialogTitle>
            <AlertDialogDescription>All current data will be replaced. This cannot be undone. Consider downloading a backup first.</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={restore} disabled={busy} data-testid="restore-confirm-btn">Replace everything</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
