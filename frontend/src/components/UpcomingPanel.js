import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { addDays, differenceInCalendarDays, format, parseISO } from "date-fns";
import { AlertTriangle, ArrowRight, CalendarDays } from "lucide-react";
import { api } from "@/lib/api";
import { StatusBadge } from "@/components/StatusBadge";

const FLAG = {
  overdue: ["Overdue", "bg-red-50 text-red-700 border-red-200"],
  behind: ["Behind schedule", "bg-[#FEF3C7] text-[#92400E] border-[#FDE68A]"],
  not_started: ["Not started", "bg-[#FEF3C7] text-[#92400E] border-[#FDE68A]"],
  on_track: ["On track", "bg-[#ECFDF5] text-[#047857] border-[#A7F3D0]"],
  ready: ["Ready", "bg-[#DCFCE7] text-[#15803D] border-[#86EFAC]"],
};

// Readiness expected by days until the planned date
export function scheduleFlag(item, today = new Date()) {
  const days = differenceInCalendarDays(parseISO(item.date), today);
  const status = item.episode?.status;
  if (status === "published" || status === "script_complete") return "ready";
  if (days < 0) return "overdue";
  if (!item.episode) return days <= 21 ? "not_started" : "on_track";
  if (days <= 7) return "behind";
  if (days <= 14 && status === "draft") return "behind";
  return "on_track";
}

export function UpcomingPanel() {
  const [items, setItems] = useState(null);
  useEffect(() => {
    const today = new Date();
    api.get("/plan", { params: { start: format(addDays(today, -60), "yyyy-MM-dd"), end: format(addDays(today, 60), "yyyy-MM-dd") } })
      .then((r) => setItems(r.data.filter((i) => i.date)
        .map((i) => ({ ...i, flag: scheduleFlag(i, today), days: differenceInCalendarDays(parseISO(i.date), today) }))
        .filter((i) => i.days >= 0 || i.flag === "overdue")
        .sort((a, b) => a.date.localeCompare(b.date))));
  }, []);
  if (!items) return null;
  const flagged = items.filter((i) => ["overdue", "behind", "not_started"].includes(i.flag)).length;

  return (
    <div className="card-warm p-6" data-testid="dashboard-upcoming">
      <div className="flex items-center justify-between mb-2">
        <h2 className="f-serif text-2xl text-[#1C1917] flex items-center gap-2"><CalendarDays className="h-5 w-5 text-[#B45309]" /> Upcoming</h2>
        <div className="flex items-center gap-3">
          {flagged > 0 && (
            <span className="flex items-center gap-1 text-xs font-semibold text-red-700" data-testid="dashboard-flagged-count">
              <AlertTriangle className="h-3.5 w-3.5" /> {flagged} need attention
            </span>
          )}
          <Link to="/planner" className="text-sm text-[#B45309] hover:underline flex items-center gap-1" data-testid="dashboard-open-planner">Planner <ArrowRight className="h-3.5 w-3.5" /></Link>
        </div>
      </div>
      {!items.length ? (
        <p className="text-stone-500 italic py-3">Nothing scheduled in the next 60 days. Plan episodes in the Planner.</p>
      ) : (
        <ul className="divide-y divide-[#EFE8DC]">
          {items.slice(0, 8).map((i) => {
            const [label, cls] = FLAG[i.flag];
            const to = i.episode_id ? `/episodes/${i.episode_id}` : "/planner";
            return (
              <li key={i.id} data-testid={`upcoming-item-${i.id}`}>
                <Link to={to} className="flex items-center gap-4 py-3 px-2 -mx-2 rounded-md hover:bg-[#F4EFE6] transition-colors">
                  <div className="w-14 text-center shrink-0">
                    <div className="eyebrow !text-[10px]">{format(parseISO(i.date), "MMM")}</div>
                    <div className="f-serif text-2xl leading-none text-[#1C1917]">{format(parseISO(i.date), "d")}</div>
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="f-serif text-lg text-[#1C1917] truncate">{i.episode?.title || i.title}</div>
                    <div className="text-xs text-stone-500">{i.days < 0 ? `${-i.days} days ago` : i.days === 0 ? "Today" : `In ${i.days} days`}</div>
                  </div>
                  {i.episode && <StatusBadge status={i.episode.status} testId={`upcoming-status-${i.id}`} />}
                  <span className={`text-[11px] font-semibold px-2 py-0.5 rounded-full border whitespace-nowrap ${cls}`} data-testid={`upcoming-flag-${i.id}`}>{label}</span>
                </Link>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
