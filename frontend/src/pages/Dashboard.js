import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowRight, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { api, fmtDate, STATUS_LABELS } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { StatusBadge } from "@/components/StatusBadge";

function EpisodeRow({ e }) {
  return (
    <Link to={`/episodes/${e.id}`} data-testid={`dashboard-episode-${e.id}`}
      className="flex items-center justify-between gap-4 py-3.5 px-2 -mx-2 rounded-md hover:bg-[#F4EFE6] transition-colors">
      <div className="min-w-0">
        <div className="f-serif text-lg text-[#1C1917] truncate">{e.episode_number ? `#${e.episode_number} · ` : ""}{e.title}</div>
        <div className="text-sm text-stone-500 truncate"><span className="f-serif italic">{e.primary_scripture}</span> · {e.topic}</div>
      </div>
      <div className="flex items-center gap-3 shrink-0">
        <span className="f-mono text-xs text-stone-500 hidden sm:inline">{fmtDate(e.updated_at)}</span>
        <StatusBadge status={e.status} testId={`dashboard-status-${e.id}`} />
      </div>
    </Link>
  );
}

export default function Dashboard() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [episodes, setEpisodes] = useState([]);
  const [meta, setMeta] = useState(null);

  useEffect(() => {
    api.get("/episodes").then((r) => setEpisodes(r.data));
    api.get("/episodes/meta").then((r) => setMeta(r.data));
  }, []);

  const inProgress = episodes.filter((e) => ["draft", "outline_approved"].includes(e.status));
  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-8 py-10 space-y-8" data-testid="dashboard">
      <section className="fade-up flex flex-col md:flex-row md:items-end justify-between gap-6">
        <div>
          <p className="eyebrow">Production desk</p>
          <h1 className="f-serif text-4xl sm:text-5xl font-semibold tracking-tight text-[#1C1917] mt-2">
            Grace and peace, {user?.name?.split(" ")[0]}.
          </h1>
          <p className="text-stone-600 mt-2 max-w-xl">Plan the next episode, finish what's in progress, or look back at what's been covered.</p>
        </div>
        <Button size="lg" className="rounded-full" onClick={() => navigate("/episodes/new")} data-testid="dashboard-new-episode-btn">
          <Plus className="h-4 w-4 mr-1" /> Start a new episode
        </Button>
      </section>

      <section className="grid grid-cols-2 md:grid-cols-4 gap-4 fade-up" style={{ animationDelay: "80ms" }}>
        {Object.entries(STATUS_LABELS).map(([k, label]) => (
          <div key={k} className="card-warm p-5" data-testid={`stat-${k}`}>
            <div className="f-serif text-4xl font-semibold text-[#1C1917]">{meta?.status_counts?.[k] ?? "–"}</div>
            <div className="text-sm text-stone-500 mt-1">{label}</div>
          </div>
        ))}
      </section>

      <section className="grid grid-cols-1 lg:grid-cols-12 gap-6 fade-up" style={{ animationDelay: "160ms" }}>
        <div className="lg:col-span-8 card-warm p-6 space-y-6">
          <div>
            <div className="flex items-center justify-between">
              <h2 className="f-serif text-2xl text-[#1C1917]">In progress</h2>
            </div>
            <div className="divide-y divide-[#EFE8DC] mt-2" data-testid="dashboard-in-progress">
              {inProgress.length ? inProgress.slice(0, 6).map((e) => <EpisodeRow key={e.id} e={e} />) : (
                <p className="text-stone-500 italic py-4">Nothing on the desk right now.</p>
              )}
            </div>
          </div>
          <div>
            <div className="flex items-center justify-between">
              <h2 className="f-serif text-2xl text-[#1C1917]">Recently updated</h2>
              <Link to="/episodes" className="text-sm text-[#B45309] hover:underline flex items-center gap-1" data-testid="dashboard-view-library">
                Full library <ArrowRight className="h-3.5 w-3.5" />
              </Link>
            </div>
            <div className="divide-y divide-[#EFE8DC] mt-2" data-testid="dashboard-recent">
              {episodes.length ? [...episodes].sort((a, b) => b.updated_at.localeCompare(a.updated_at)).slice(0, 6)
                .map((e) => <EpisodeRow key={e.id} e={e} />) : <p className="text-stone-500 italic py-4">No episodes yet. Start your first one.</p>}
            </div>
          </div>
        </div>
        <aside className="lg:col-span-4 space-y-6">
          <TagCloud title="Themes covered" items={meta?.themes} param="theme" testId="dashboard-themes" />
          <TagCloud title="Books of the Bible" items={meta?.books} param="book" testId="dashboard-books" />
        </aside>
      </section>
    </div>
  );
}

function TagCloud({ title, items, param, testId }) {
  return (
    <div className="card-warm p-6" data-testid={testId}>
      <h3 className="f-serif text-xl text-[#1C1917] mb-4">{title}</h3>
      {items?.length ? (
        <div className="flex flex-wrap gap-2">
          {items.slice(0, 18).map((t) => (
            <Link key={t.name} to={`/episodes?${param}=${encodeURIComponent(t.name)}`}
              className="px-3 py-1 rounded-full bg-[#F4EFE6] border border-[#E7E0D6] text-sm text-[#44403C] hover:border-[#B45309] transition-colors capitalize">
              {t.name} <span className="f-mono text-xs text-stone-500">{t.count}</span>
            </Link>
          ))}
        </div>
      ) : <p className="text-sm text-stone-500 italic">Appears as episodes are added.</p>}
    </div>
  );
}
