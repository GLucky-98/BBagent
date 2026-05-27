import { UserCircle2 } from "lucide-react";

export function UserMenu() {
  return (
    <button className="flex items-center justify-center w-12 h-12 shrink-0 hover:bg-[--color-secondary] rounded-md transition-colors">
      <UserCircle2 className="w-5 h-5 text-[--color-muted-foreground]" />
    </button>
  );
}
