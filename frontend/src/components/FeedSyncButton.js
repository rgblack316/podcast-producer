import { useState } from "react";
import { Loader2, Rss } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { api, errMsg } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";

export function FeedSyncButton({ episode, what, onChange }) {
  const { user } = useAuth();
  const [busy, setBusy] = useState(false);
  if (!episode.rss_guid || user?.role !== "admin") return null;
  const label = what === "artwork" ? "Import artwork from feed" : "Import show notes from feed";
  const run = async () => {
    setBusy(true);
    try {
      const { data } = await api.post(`/rss/episode/${episode.id}/sync`, { artwork: what === "artwork", show_notes: what === "show_notes" });
      if (data[what]) toast.success(what === "artwork" ? "Artwork imported from the feed" : "Show notes imported from the feed");
      else toast.info(data.note || (what === "artwork" ? "Feed artwork is already in the gallery" : "Show notes were edited here, so the feed copy wasn't applied"));
      onChange((await api.get(`/episodes/${episode.id}`)).data);
    } catch (e) { toast.error(errMsg(e)); } finally { setBusy(false); }
  };
  return (
    <Button variant="outline" size="sm" className="bg-[#FFFDF9]" onClick={run} disabled={busy} data-testid={`feed-sync-${what}-btn`}>
      {busy ? <Loader2 className="h-4 w-4 mr-1.5 animate-spin" /> : <Rss className="h-4 w-4 mr-1.5" />} {label}
    </Button>
  );
}
