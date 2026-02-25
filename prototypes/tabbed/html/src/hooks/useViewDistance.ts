import { useEffect, useState } from "react";

export type ViewDistance = "phone" | "desk" | "tv";

/**
 * Detect viewing distance from viewport width.
 *   phone: <768px
 *   desk:  768–1919px
 *   tv:    >=1920px
 */
export function useViewDistance(): ViewDistance {
  const [distance, setDistance] = useState<ViewDistance>(() => classify(window.innerWidth));

  useEffect(() => {
    const mqPhone = window.matchMedia("(max-width: 767px)");
    const mqTv = window.matchMedia("(min-width: 1920px)");

    const update = () => setDistance(classify(window.innerWidth));

    mqPhone.addEventListener("change", update);
    mqTv.addEventListener("change", update);
    return () => {
      mqPhone.removeEventListener("change", update);
      mqTv.removeEventListener("change", update);
    };
  }, []);

  return distance;
}

function classify(w: number): ViewDistance {
  if (w < 768) return "phone";
  if (w >= 1920) return "tv";
  return "desk";
}
