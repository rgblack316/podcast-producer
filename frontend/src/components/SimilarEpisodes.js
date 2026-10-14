import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { AlertTriangle } from "lucide-react";
import { api } from "@/lib/api";
import { StatusBadge } from "@/components/StatusBadge";

export function SimilarEpisodes({ scripture, themes, topic, exclude }) {
  const [items, setItems] = useState([]);

  useEffect(() => {
    const t = setTimeout(() => {
      if (!scripture && !themes && !topic) return setItems([]);
      api.get("/episodes/similar", { params: { scripture, themes, topic, exclude } })
        .then((r) => setItems(r.data)).catch(() => setItems([]));
    }, 500);
    return () => clearTimeout(t);
  }, [scripture, themes, topic, exclude]);

  if (!items.length) {
    return (
      <p className="text-sm text-stone-500 italic" data-testid="similar-empty">
        No past episodes overlap with this scripture, theme or topic yet.
      </p>
    );
  }
  return (
    <div className="rounded-lg border border-[#FDE68A] bg-[#FEF3C7]/60 p-4 space-y-3" data-testid="intake-similar-warning-banner">
      <div className="flex items-center gap-2 text-[#92400E] font-semibold text-sm">
        <AlertTriangle className="h-4 w-4" /> {items.length} related past episode{items.length > 1 ? "s" : ""}
      </div>
      <ul className="space-y-2">
        {items.map((e) => (
          <li key={e.id} className="bg-[#FFFDF9] rounded-md border border-[#E7E0D6] p-3" data-testid={`similar-item-${e.id}`}>
            <div className="flex items-start justify-between gap-2">
              <Link to={`/episodes/${e.id}`} className="f-serif text-base font-medium text-[#1C1917] hover:text-[#B45309]">
                {e.episode_number ? `#${e.episode_number} · ` : ""}{e.title}
              </Link>
              <StatusBadge status={e.status} testId={`similar-status-${e.id}`} />
            </div>
            <div className="f-serif italic text-sm text-stone-600">{e.primary_scripture}</div>
            <div className="text-xs text-[#92400E] mt-1">{(e.reasons || []).join(" · ")}</div>
          </li>
        ))}
      </ul>
    </div>
  );
}
