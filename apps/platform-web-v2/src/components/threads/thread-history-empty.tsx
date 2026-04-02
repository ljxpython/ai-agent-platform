import { PageStateEmpty } from "@/components/platform/page-state";

export function ThreadHistoryEmpty({ message }: { message: string }) {
  return <PageStateEmpty className="mt-0" message={message} />;
}
