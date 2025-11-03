import { useEffect, useState } from "react";
// FIXME  MS8yOmFIVnBZMlhtblk3a3ZiUG1yS002ZG5SVU5nPT06ZTlhNGZiNjk=

export function useMediaQuery(query: string) {
  const [matches, setMatches] = useState(false);

  useEffect(() => {
    const media = window.matchMedia(query);
    setMatches(media.matches);

    const listener = (e: MediaQueryListEvent) => setMatches(e.matches);
    media.addEventListener("change", listener);
    return () => media.removeEventListener("change", listener);
  }, [query]);

  return matches;
}
