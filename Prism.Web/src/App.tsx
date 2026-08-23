import { SelectedClaimProvider } from "@/contexts/SelectedClaimContext";
import { AppShell } from "@/components/AppShell";
import ChatMode from "@/components/ChatMode";

// Slice 1 ships the Matrix UI only. ChatMode (Slice 3) is preserved but
// unreachable until a real entry point is designed for it.
const isChatMode = false;

function App() {
  if (isChatMode) {
    return <ChatMode />;
  }

  return (
    <SelectedClaimProvider>
      <AppShell />
    </SelectedClaimProvider>
  );
}

export default App;
