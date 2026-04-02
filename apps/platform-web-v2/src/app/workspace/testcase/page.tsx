import { redirect } from "next/navigation";

type TestcaseIndexPageProps = {
  searchParams?: Promise<Record<string, string | string[] | undefined>>;
};

export default async function TestcaseIndexPage({
  searchParams,
}: TestcaseIndexPageProps) {
  const resolvedSearchParams = searchParams ? await searchParams : {};
  const nextParams = new URLSearchParams();

  for (const [key, value] of Object.entries(resolvedSearchParams)) {
    if (typeof value === "string" && value.trim()) {
      nextParams.set(key, value.trim());
    }
  }

  const query = nextParams.toString();
  redirect(
    query ? `/workspace/testcase/generate?${query}` : "/workspace/testcase/generate",
  );
}
