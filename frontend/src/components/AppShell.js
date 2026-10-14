import { Link, NavLink, useNavigate } from "react-router-dom";
import { LogOut, Plus, UserRound } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useAuth } from "@/context/AuthContext";

const navCls = ({ isActive }) =>
  `px-3 py-1.5 rounded-full text-sm font-medium transition-colors ${
    isActive ? "bg-[#F0E9DD] text-[#1C1917]" : "text-[#57534E] hover:text-[#1C1917] hover:bg-[#F4EFE6]"
  }`;

export default function AppShell({ children }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  return (
    <div className="min-h-screen paper-grain">
      <header className="sticky top-0 z-50 backdrop-blur-md bg-[#FAF7F2]/90 border-b border-[#E7E0D6]">
        <div className="max-w-[1600px] mx-auto px-4 sm:px-6 py-3 flex items-center gap-4">
          <Link to="/" className="flex items-center gap-2.5 shrink-0" data-testid="brand-link">
            <img src="/logo-mark.png" alt="Bible Bytes logo" className="h-9 w-9 rounded-md border border-[#E2DACD] shadow-sm" data-testid="header-logo" />
            <span className="f-serif text-xl font-semibold tracking-tight text-[#1C1917]">
              Bible Bytes <span className="italic font-normal text-[#B45309]">Producer</span>
            </span>
          </Link>
          <nav className="hidden md:flex items-center gap-1 ml-6">
            <NavLink to="/" end className={navCls} data-testid="nav-dashboard">Dashboard</NavLink>
            <NavLink to="/episodes" end className={navCls} data-testid="nav-library">Library</NavLink>
            <NavLink to="/coverage" className={navCls} data-testid="nav-coverage">Coverage</NavLink>
            <NavLink to="/planner" className={navCls} data-testid="nav-planner">Planner</NavLink>
            <NavLink to="/series" className={navCls} data-testid="nav-series">Series</NavLink>
            {user?.role === "admin" && (
              <NavLink to="/import" className={navCls} data-testid="nav-import">Import</NavLink>
            )}
            {user?.role === "admin" && (
              <NavLink to="/settings" className={navCls} data-testid="nav-settings">Settings</NavLink>
            )}
          </nav>
          <div className="ml-auto flex items-center gap-2">
            <Button onClick={() => navigate("/episodes/new")} className="rounded-full" data-testid="header-new-episode-btn">
              <Plus className="h-4 w-4 mr-1" /> New episode
            </Button>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="outline" size="icon" className="rounded-full bg-[#FFFDF9]" data-testid="user-menu-trigger">
                  <UserRound className="h-4 w-4" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-56">
                <DropdownMenuLabel>
                  <div className="text-sm" data-testid="user-menu-name">{user?.name}</div>
                  <div className="f-mono text-xs text-stone-500">@{user?.username} · {user?.role}</div>
                </DropdownMenuLabel>
                <DropdownMenuSeparator />
                <DropdownMenuItem className="md:hidden" onClick={() => navigate("/episodes")}>Library</DropdownMenuItem>
                <DropdownMenuItem className="md:hidden" onClick={() => navigate("/coverage")}>Coverage</DropdownMenuItem>
                <DropdownMenuItem className="md:hidden" onClick={() => navigate("/planner")}>Planner</DropdownMenuItem>
                <DropdownMenuItem className="md:hidden" onClick={() => navigate("/series")}>Series</DropdownMenuItem>
                {user?.role === "admin" && (
                  <DropdownMenuItem className="md:hidden" onClick={() => navigate("/import")}>Import</DropdownMenuItem>
                )}
                {user?.role === "admin" && (
                  <DropdownMenuItem className="md:hidden" onClick={() => navigate("/settings")}>Settings</DropdownMenuItem>
                )}
                <DropdownMenuItem onClick={() => navigate("/account")} data-testid="user-menu-account">My account</DropdownMenuItem>
                <DropdownMenuItem onClick={logout} data-testid="logout-btn">
                  <LogOut className="h-4 w-4 mr-2" /> Sign out
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>
      </header>
      <main>{children}</main>
    </div>
  );
}
