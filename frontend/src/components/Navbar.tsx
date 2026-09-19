import { LocaleSwitcher } from "@/components/LocaleSwitcher";
import { Link } from "@/i18n/navigation";

export function Navbar({ children }: { children?: React.ReactNode }) {
  return (
    <header className="border-b border-slate-200 bg-white">
      <div className="mx-auto flex max-w-5xl items-center justify-between gap-4 px-4 py-3">
        <Link href="/" className="text-lg font-semibold">
          Jac Rag
        </Link>
        <div className="flex items-center gap-3">
          <LocaleSwitcher />
          {children}
        </div>
      </div>
    </header>
  );
}
