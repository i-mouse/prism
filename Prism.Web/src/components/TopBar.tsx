import { Menu, ChevronDown } from "lucide-react";
import { PrismLogo } from "@/components/PrismLogo";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "@/lib/AuthContext";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

/**
 * TopBar is only rendered on mobile (lg:hidden on the wrapper in AppShell).
 * On desktop the sidebar carries the logo and the main content has its own header.
 */
export function TopBar({ onMenuClick }: { onMenuClick?: () => void }) {
  const { user, signOut } = useAuth();
  const navigate = useNavigate();

  const isGuest = user?.provider === "guest";
  const avatarInitial = isGuest ? "G" : user?.name?.[0]?.toUpperCase() ?? "?";

  const handleSignOut = async () => {
    await signOut();
    navigate("/login");
  };

  return (
    <header className="flex h-14 shrink-0 items-center justify-between border-b border-hairline bg-surface px-4 py-3 lg:hidden">
      <div className="flex items-center gap-2">
        <button
          onClick={onMenuClick}
          className="mr-1 text-ink-secondary hover:text-ink"
          aria-label="Open menu"
        >
          <Menu className="h-6 w-6" />
        </button>
        <Link to="/" className="flex items-center gap-2">
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
              <ChevronDown className="h-4 w-4 text-ink-tertiary" />
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
