"use client";
import { useEffect, useRef, useState } from "react";

export default function CountUp({
  value, decimals = 0, prefix = "", suffix = "",
}: { value: number; decimals?: number; prefix?: string; suffix?: string }) {
  const [d, setD] = useState(0);
  const raf = useRef<number>();
  useEffect(() => {
    if (typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion:reduce)").matches) {
      setD(value);
      return;
    }
    let start: number | null = null;
    const step = (t: number) => {
      if (start === null) start = t;
      const p = Math.min((t - start) / 900, 1);
      setD(value * (1 - Math.pow(1 - p, 3)));
      if (p < 1) raf.current = requestAnimationFrame(step);
    };
    raf.current = requestAnimationFrame(step);
    return () => { if (raf.current) cancelAnimationFrame(raf.current); };
  }, [value]);
  return <>{prefix}{d.toFixed(decimals)}{suffix}</>;
}
