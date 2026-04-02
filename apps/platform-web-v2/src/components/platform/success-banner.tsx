import type { HTMLAttributes } from "react";

import { StateBanner } from "@/components/platform/state-banner";

export function SuccessBanner(
  props: Omit<HTMLAttributes<HTMLDivElement>, "children"> & { message: string },
) {
  return <StateBanner {...props} variant="success" />;
}
