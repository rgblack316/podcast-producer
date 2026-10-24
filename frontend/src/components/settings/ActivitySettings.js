import { useCallback, useEffect, useState } from "react";
import { Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { api, errMsg } from "@/lib/api";

const LABELS = {
  login: "Signed in", login_failed: "Failed sign-in", login_locked: "Sign-in blocked (too many tries)", logout: "Signed out",
  password_changed: "Changed password", password_reset: "Password reset by admin", user_created: "User created",
  user_updated: "User changed", user_deleted: "User deleted", settings_updated: "Settings changed",
  backup_download: "Backup downloaded", backup_restored: "Backup restored", setup_completed: "Setup completed",
  setup_restore: "Restored during setup", series_deleted: "Series deleted",
};
const PAGE = 50;

export function ActivitySettings() {
  const [rows, setRows] = useState([]);
  const [more, setMore] = useState(false);
  const [busy, setBusy] = useState(true);
  const [err, setErr] = useState("");

  const load = useCallback(async (skip) => {
    setBusy(true);
    try {
      const { data } = await api.get("/settings/audit", { params: { limit: PAGE, skip } });
      setRows((prev) => (skip ? [...prev, ...data] : data));
      setMore(data.length === PAGE);
      setErr("");
    } catch (e) { setErr(errMsg(e)); } finally { setBusy(false); }
  }, []);
  useEffect(() => { load(0); }, [load]);

  return (
    <div className="space-y-4" data-testid="activity-panel">
      <p className="text-sm text-stone-600">Sign-ins, account and settings changes, and backups. Passwords and API keys are never recorded. Entries are kept for a year.</p>
      {err && <p className="text-sm text-red-700">{err}</p>}
      <div className="rounded-2xl border border-[#E7E0D2] bg-[#FFFDF9] divide-y divide-[#EFE9DC]">
        {rows.map((r, i) => (
          <div key={i} className="px-4 py-3 flex flex-wrap gap-x-4 gap-y-1 text-sm">
            <span className="f-mono text-[11px] text-stone-500 w-44 shrink-0">{new Date(r.at).toLocaleString()}</span>
            <span className="font-medium text-[#1C1917]">{LABELS[r.action] || r.action}</span>
            <span className="text-stone-600">{[r.actor && `by ${r.actor}`, r.target && `· ${r.target}`].filter(Boolean).join(" ")}</span>
            <span className="f-mono text-[11px] text-stone-400 ml-auto">{r.ip}</span>
          </div>
        ))}
        {!busy && rows.length === 0 && !err && <div className="px-4 py-6 text-sm text-stone-500">Nothing recorded yet.</div>}
      </div>
      {busy && <Loader2 className="h-4 w-4 animate-spin text-stone-500" />}
      {more && !busy && <Button variant="outline" className="rounded-full" onClick={() => load(rows.length)}>Show more</Button>}
    </div>
  );
}
