import { SelectedClaimProvider } from "@/contexts/SelectedClaimContext";
import { AppShell } from "@/components/AppShell";
import { AuthProvider } from "@/lib/AuthContext";
import { RequireAuth } from "@/components/RequireAuth";
import { Login } from "@/pages/Login";
import { Privacy } from "@/pages/Privacy";
import { Terms } from "@/pages/Terms";
import { Routes, Route } from "react-router-dom";

function App() {
  return (
    <AuthProvider>
      <SelectedClaimProvider>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/privacy" element={<Privacy />} />
          <Route path="/terms" element={<Terms />} />
          <Route
            path="/"
            element={
              <RequireAuth>
                <AppShell />
              </RequireAuth>
            }
          />
          <Route
            path="/paper/:paperId"
            element={
              <RequireAuth>
                <AppShell />
              </RequireAuth>
            }
          />
        </Routes>
      </SelectedClaimProvider>
    </AuthProvider>
  );
}

export default App;
