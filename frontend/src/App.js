import "@/App.css";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { Toaster } from "@/components/ui/sonner";
import { AuthProvider, useAuth } from "@/context/AuthContext";
import AppShell from "@/components/AppShell";
import Login from "@/pages/Login";
import Dashboard from "@/pages/Dashboard";
import NewEpisode from "@/pages/NewEpisode";
import Episode from "@/pages/Episode";
import Library from "@/pages/Library";
import Settings from "@/pages/Settings";
import Account from "@/pages/Account";
import Coverage from "@/pages/Coverage";
import Planner from "@/pages/Planner";
import RssImport from "@/pages/RssImport";

function Protected({ children, admin }) {
  const { user } = useAuth();
  if (user === null) {
    return (
      <div className="min-h-screen grid place-items-center" data-testid="auth-loading">
        <span className="f-serif italic text-stone-500">Opening the writing room…</span>
      </div>
    );
  }
  if (!user) return <Navigate to="/login" replace />;
  if (admin && user.role !== "admin") return <Navigate to="/" replace />;
  return <AppShell>{children}</AppShell>;
}

function LoginRoute() {
  const { user } = useAuth();
  if (user) return <Navigate to="/" replace />;
  return <Login />;
}

function App() {
  return (
    <div className="App">
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/login" element={<LoginRoute />} />
            <Route path="/" element={<Protected><Dashboard /></Protected>} />
            <Route path="/episodes" element={<Protected><Library /></Protected>} />
            <Route path="/episodes/new" element={<Protected><NewEpisode /></Protected>} />
            <Route path="/episodes/:id" element={<Protected><Episode /></Protected>} />
            <Route path="/coverage" element={<Protected><Coverage /></Protected>} />
            <Route path="/planner" element={<Protected><Planner /></Protected>} />
            <Route path="/import" element={<Protected admin><RssImport /></Protected>} />
            <Route path="/settings" element={<Protected admin><Settings /></Protected>} />
            <Route path="/account" element={<Protected><Account /></Protected>} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </BrowserRouter>
        <Toaster position="bottom-right" richColors />
      </AuthProvider>
    </div>
  );
}

export default App;
