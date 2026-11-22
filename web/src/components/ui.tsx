// Piezas básicas de la interfaz (botones, selector segmentado, tarjeta, chip de color).
import clsx from "clsx";
import { Info } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useId, useState, type ButtonHTMLAttributes, type ReactNode } from "react";
import { batchColor } from "../lib/colors";

type Variant = "primary" | "secondary" | "ghost";

const VARIANTS: Record<Variant, string> = {
  primary: "bg-ink text-white hover:bg-ink-soft shadow-card",
  secondary: "bg-surface text-ink border border-line-strong hover:border-ink/40 shadow-card",
  ghost: "text-ink-soft hover:bg-sunken",
};

export function Button({ variant = "secondary", className, ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant }) {
  return (
    <button
      type="button"
      className={clsx(
        "inline-flex items-center justify-center gap-2 rounded-lg px-3.5 py-2 text-sm font-medium transition-colors",
        "disabled:cursor-not-allowed disabled:opacity-45",
        VARIANTS[variant],
        className,
      )}
      {...props}
    />
  );
}

export function Segmented<T extends string>({ value, options, onChange, label }: {
  value: T;
  options: { value: T; label: ReactNode; disabled?: boolean; title?: string }[];
  onChange: (value: T) => void;
  label: string;
}) {
  return (
    <div role="radiogroup" aria-label={label} className="inline-flex rounded-lg bg-sunken p-1 ring-1 ring-line">
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          role="radio"
          aria-checked={o.value === value}
          disabled={o.disabled}
          title={o.title}
          onClick={() => onChange(o.value)}
          className={clsx(
            "rounded-md px-3 py-1.5 text-sm font-medium transition-all disabled:opacity-40",
            o.value === value ? "bg-surface text-ink shadow-card" : "text-muted hover:text-ink",
          )}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

export function Card({ className, children }: { className?: string; children: ReactNode }) {
  return <div className={clsx("rounded-xl border border-line bg-surface shadow-card", className)}>{children}</div>;
}

export function BatchDot({ batch, size = 10 }: { batch: number; size?: number }) {
  return <span aria-hidden className="inline-block shrink-0 rounded-full" style={{ width: size, height: size, background: batchColor(batch) }} />;
}

export function ResourceChip({ name }: { name: string }) {
  return (
    <span className="inline-flex items-center rounded-md bg-sunken px-1.5 py-0.5 font-mono text-[11.5px] text-ink-soft ring-1 ring-line">
      {name}
    </span>
  );
}

/** Ícono ⓘ que muestra una explicación al pasar el cursor, al enfocarlo con el teclado o al tocarlo. */
export function InfoTip({ label, children }: { label: string; children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const id = useId();
  return (
    <span className="relative inline-flex align-middle" onMouseEnter={() => setOpen(true)} onMouseLeave={() => setOpen(false)}>
      <button
        type="button"
        aria-label={label}
        aria-expanded={open}
        aria-describedby={open ? id : undefined}
        onClick={() => setOpen((o) => !o)}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        onKeyDown={(e) => { if (e.key === "Escape") setOpen(false); }}
        className={clsx("grid size-7 place-items-center rounded-full transition-colors", open ? "bg-accent-soft text-accent" : "text-faint hover:text-ink")}
      >
        <Info className="size-[18px]" />
      </button>
      <AnimatePresence>
        {open && (
          <motion.div
            id={id}
            role="tooltip"
            initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} transition={{ duration: 0.12 }}
            className="absolute left-0 top-full z-40 mt-2 w-[min(22rem,80vw)] rounded-xl border border-line bg-surface p-4 text-left text-sm font-normal leading-relaxed tracking-normal text-ink-soft shadow-pop"
          >
            {children}
          </motion.div>
        )}
      </AnimatePresence>
    </span>
  );
}

export function StepTitle({ number, title, info }: { number?: number; title: string; info?: ReactNode }) {
  return (
    <div className="relative z-30 mb-6">
      {number && <p className="mb-1 text-sm font-medium text-accent">Paso {number} de 3</p>}
      <h1 className="flex items-center gap-2 text-[28px] font-semibold leading-tight tracking-tight text-ink">
        {title}
        {info && <InfoTip label={`Qué hacer en este paso: ${title}`}>{info}</InfoTip>}
      </h1>
    </div>
  );
}
