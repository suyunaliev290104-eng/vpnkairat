import type { ButtonHTMLAttributes, ReactNode } from "react";
import { haptic } from "../tg";

type BtnProps = ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "secondary" | "ghost"; loading?: boolean };

export function Button({ variant = "primary", loading, children, onClick, className = "", ...rest }: BtnProps) {
  return (
    <button
      {...rest}
      className={`btn btn-${variant} ${className}`}
      disabled={loading || rest.disabled}
      onClick={(e) => { haptic(); onClick?.(e); }}
    >
      {loading ? <span className="spinner" /> : children}
    </button>
  );
}

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`card ${className}`}>{children}</div>;
}

export function Row({ icon, title, subtitle, onClick, right }: {
  icon: string; title: string; subtitle?: string; onClick?: () => void; right?: ReactNode;
}) {
  return (
    <button className="row" onClick={() => { haptic(); onClick?.(); }}>
      <span className="row-icon">{icon}</span>
      <span className="row-text">
        <span className="row-title">{title}</span>
        {subtitle && <span className="row-sub">{subtitle}</span>}
      </span>
      {right ?? <span className="row-chevron">›</span>}
    </button>
  );
}

export function Loader() {
  return <div className="center"><span className="spinner big" /></div>;
}
