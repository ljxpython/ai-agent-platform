import { Card } from "@/components/ui/card";

export function ErrorState({
  description,
  title,
}: {
  description: string;
  title: string;
}) {
  return (
    <Card
      className="px-6 py-10 text-center"
      style={{
        background: "var(--status-danger-background)",
        borderColor: "transparent",
        color: "var(--status-danger-foreground)",
      }}
    >
      <h3 className="text-lg font-semibold">{title}</h3>
      <p className="mx-auto mt-3 max-w-xl text-sm leading-7">{description}</p>
    </Card>
  );
}
