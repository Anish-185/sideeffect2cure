import { useEffect, useRef, useState } from "react";

function prefersReducedMotion(): boolean {
  return typeof window !== "undefined" && Boolean(window.matchMedia?.("(prefers-reduced-motion: reduce)").matches);
}

/** Scroll-driven effects are progressive enhancement: where the observer is
 * unavailable, content must simply be shown rather than stuck hidden. */
function canObserve(): boolean {
  return typeof IntersectionObserver !== "undefined";
}

/**
 * Slow parallax drift for background artwork. Writes the transform straight
 * to the node (no re-render per frame) and only runs while the element is
 * near the viewport. `strength` is how far it drifts, in px, across a full
 * screen of scrolling — keep it small; this should be felt, not seen.
 */
export function useParallax<T extends HTMLElement>(strength = 60) {
  const ref = useRef<T | null>(null);

  useEffect(() => {
    const node = ref.current;
    if (!node || prefersReducedMotion() || !canObserve()) return;

    let visible = false;
    let frame = 0;

    function apply() {
      frame = 0;
      const el = ref.current;
      if (!el) return;
      const rect = el.getBoundingClientRect();
      // -1 (below the fold) .. 1 (above it), 0 when centred.
      const progress = (window.innerHeight / 2 - (rect.top + rect.height / 2)) / window.innerHeight;
      el.style.transform = `translate3d(0, ${(progress * strength).toFixed(2)}px, 0)`;
    }

    function onScroll() {
      if (!visible || frame) return;
      frame = requestAnimationFrame(apply);
    }

    const observer = new IntersectionObserver(
      ([entry]) => {
        visible = entry.isIntersecting;
        if (visible) apply();
      },
      { rootMargin: "200px 0px" },
    );
    observer.observe(node);
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll, { passive: true });

    return () => {
      observer.disconnect();
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onScroll);
      if (frame) cancelAnimationFrame(frame);
    };
  }, [strength]);

  return ref;
}

/**
 * One-shot section reveal. Returns a ref and whether the element has entered
 * the viewport yet — it never flips back, so content stays put once read.
 * Under reduced motion it starts revealed.
 */
export function useReveal<T extends HTMLElement>(threshold = 0.15) {
  const ref = useRef<T | null>(null);
  const [revealed, setRevealed] = useState(() => prefersReducedMotion() || !canObserve());

  useEffect(() => {
    const node = ref.current;
    if (!node || prefersReducedMotion() || !canObserve()) return;

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setRevealed(true);
          observer.disconnect();
        }
      },
      { threshold, rootMargin: "0px 0px -8% 0px" },
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, [threshold]);

  return { ref, revealed };
}
