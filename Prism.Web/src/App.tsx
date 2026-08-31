import { SelectedClaimProvider } from "@/contexts/SelectedClaimContext";
import { AppShell } from "@/components/AppShell";

function App() {
  return (
    <SelectedClaimProvider>
      <AppShell />
    </SelectedClaimProvider>
  );
}

export default App;
