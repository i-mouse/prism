import { SelectedClaimProvider } from "@/contexts/SelectedClaimContext";
import { AppShell } from "@/components/AppShell";
import { Routes, Route } from "react-router-dom";

function App() {
  return (
    <SelectedClaimProvider>
      <Routes>
        <Route path="/" element={<AppShell />} />
        <Route path="/paper/:paperId" element={<AppShell />} />
      </Routes>
    </SelectedClaimProvider>
  );
}

export default App;
