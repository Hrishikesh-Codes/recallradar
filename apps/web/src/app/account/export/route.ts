import { getViewer, userFetch } from "@/lib/api/server";

/** Download everything we hold about you, as JSON (SPEC §11). */
export async function GET() {
  const viewer = await getViewer();
  if (!viewer) return new Response("Sign in first.", { status: 401 });
  const data = await userFetch<unknown>(viewer.id, "/v1/me/export");
  return new Response(JSON.stringify(data, null, 2), {
    headers: {
      "Content-Type": "application/json",
      "Content-Disposition": 'attachment; filename="recallradar-export.json"',
      "Cache-Control": "no-store",
    },
  });
}
