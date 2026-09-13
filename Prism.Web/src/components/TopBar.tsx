import { ChevronDown, Menu } from "lucide-react";
import { PrismLogo } from "@/components/PrismLogo";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "@/lib/AuthContext";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

export function TopBar({ onMenuClick }: { onMenuClick?: () => void }) {
  const { user, signOut } = useAuth();
  const navigate = useNavigate();

  const isGuest = user?.provider === "guest";
  const avatarInitial = isGuest ? "G" : user?.name?.[0]?.toUpperCase() ?? "?";

  const handleSignOut = async () => {
    await signOut();
    // For guest users signOut() resolves synchronously (no redirect).
    // For Google users signOut() calls MSAL logoutRedirect() and navigates away,
    // so the navigate below only runs for guests.
    navigate("/login");
  };

  return (
    <header className="flex h-14 shrink-0 items-center justify-between border-b border-hairline bg-surface px-4 md:px-6 py-3">
      <div className="flex items-center gap-2">
        <button onClick={onMenuClick} className="mr-2 lg:hidden text-ink-secondary hover:text-ink">
          <Menu className="h-6 w-6" />
        </button>
        <Link to="/" className="flex items-center gap-2" onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}>
          <PrismLogo className="h-6 w-6" />
          <span className="font-sans font-semibold text-ink">Prism</span>
        </Link>
      </div>

      {user ? (
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button className="flex items-center gap-2 outline-none">
              <div className="flex h-8 w-8 items-center justify-center rounded-full bg-surface-subtle text-sm font-medium text-ink">
                {avatarInitial}
              </div>
              <div className="hidden items-center gap-1 md:flex">
                <span className="text-sm text-ink">{isGuest ? "Guest" : user.name}</span>
                <ChevronDown className="h-4 w-4 text-ink-tertiary" />
              </div>
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent>
            {isGuest && (
              <DropdownMenuItem asChild>
                <Link to="/login">Sign in</Link>
              </DropdownMenuItem>
            )}
            <DropdownMenuItem onSelect={handleSignOut}>Sign out</DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      ) : (
        <Link to="/login" className="font-sans text-sm font-medium text-brand hover:text-brand-hover">
          Sign in
        </Link>
      )}
    </header>
  );
}
