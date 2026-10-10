import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const encoder = new TextEncoder();

async function verifySignature(
  rawBody: string,
  signature: string | null,
  secret: string,
): Promise<boolean> {
  if (!signature?.startsWith("sha256=")) return false;
  const key = await crypto.subtle.importKey(
    "raw",
    encoder.encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const digest = new Uint8Array(
    await crypto.subtle.sign("HMAC", key, encoder.encode(rawBody)),
  );
  const expected = `sha256=${Array.from(digest, (byte) =>
    byte.toString(16).padStart(2, "0")
  ).join("")}`;
  if (signature.length !== expected.length) return false;
  let difference = 0;
  for (let index = 0; index < signature.length; index++) {
    difference |= signature.charCodeAt(index) ^ expected.charCodeAt(index);
  }
  return difference === 0;
}

Deno.serve(async (request: Request) => {
  if (request.method !== "POST") {
    return new Response("Method not allowed", { status: 405 });
  }

  const webhookSecret = Deno.env.get("GITHUB_WEBHOOK_SECRET");
  const supabaseUrl = Deno.env.get("SUPABASE_URL");
  const serviceRoleKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
  if (!webhookSecret || !supabaseUrl || !serviceRoleKey) {
    console.error("Missing GitHub webhook or Supabase server configuration.");
    return new Response("Server configuration error", { status: 500 });
  }

  const rawBody = await request.text();
  if (
    !await verifySignature(
      rawBody,
      request.headers.get("x-hub-signature-256"),
      webhookSecret,
    )
  ) {
    return new Response("Invalid signature", { status: 401 });
  }

  const event = request.headers.get("x-github-event");
  if (event !== "pull_request") {
    return Response.json({ ignored: true, reason: "unsupported_event" });
  }

  let payload: {
    action?: string;
    pull_request?: { number?: number; merged?: boolean; base?: { repo?: { full_name?: string } } };
    repository?: { full_name?: string };
  };
  try {
    payload = JSON.parse(rawBody);
  } catch {
    return new Response("Invalid JSON payload", { status: 400 });
  }

  if (payload.action !== "closed") {
    return Response.json({ ignored: true, reason: "unsupported_action" });
  }
  const pullRequest = payload.pull_request;
  const fullName = pullRequest?.base?.repo?.full_name ??
    payload.repository?.full_name;
  const match = fullName?.match(/^([^/]+)\/([^/]+)$/);
  if (!pullRequest?.number || !match) {
    return new Response("Missing pull request repository or number", {
      status: 400,
    });
  }

  const supabase = createClient(supabaseUrl, serviceRoleKey, {
    auth: { persistSession: false, autoRefreshToken: false },
  });
  const { data, error } = await supabase.rpc("complete_merged_pr", {
    p_github_owner: match[1],
    p_github_repo: match[2],
    p_github_pr_number: pullRequest.number,
    p_merged: pullRequest.merged === true,
  });
  if (error) {
    console.error("Could not process merged pull request:", error.message);
    return new Response("Could not update contribution", { status: 500 });
  }

  return Response.json({ result: data });
});
