import { Card } from "@/components/ui/card";

export function EmptyState({
  description,
  title,
}: {
  description: string;
  title: string;
}) {
  return (
    <Card className="px-6 py-10 text-center">
      <h3 className="text-lg font-semibold text-[var(--foreground)]">{title}</h3>
      <p className="mx-auto mt-3 max-w-xl text-sm leading-7 text-[var(--muted-foreground)]">{description}</p>
    </Card>
  );
}
