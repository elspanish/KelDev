import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

Deno.serve(async (request: Request) => {
  if (request.method !== "POST") {
    return new Response("Method not allowed", { status: 405 });
  }

  const authorization = request.headers.get("authorization");
  const supabaseUrl = Deno.env.get("SUPABASE_URL");
  const anonKey = Deno.env.get("SUPABASE_ANON_KEY");
  const serviceRoleKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
  if (!authorization || !supabaseUrl || !anonKey || !serviceRoleKey) {
    return new Response("Missing authorization or server configuration", {
      status: 401,
    });
  }

  let body: { task_id?: string };
  try {
    body = await request.json();
  } catch {
    return new Response("Invalid JSON payload", { status: 400 });
  }
  if (!body.task_id) {
    return new Response("Missing task_id", { status: 400 });
  }

  const userClient = createClient(supabaseUrl, anonKey, {
    global: { headers: { Authorization: authorization } },
    auth: { persistSession: false, autoRefreshToken: false },
  });
  const { data: userData, error: userError } = await userClient.auth.getUser();
  if (userError || !userData.user) {
    return new Response("Invalid user session", { status: 401 });
  }

  const adminClient = createClient(supabaseUrl, serviceRoleKey, {
    auth: { persistSession: false, autoRefreshToken: false },
  });
  const { data: contributions, error: contributionError } = await adminClient
    .from("contributions")
    .select(
      "github_owner,github_repo,github_pr_number,usuario_id,estado",
    )
    .eq("task_id", body.task_id)
    .eq("usuario_id", userData.user.id)
    .limit(10);
  if (contributionError) {
    console.error("Could not load contribution:", contributionError.message);
    return new Response("Could not load contribution", { status: 500 });
  }
  const contribution = contributions?.find((item) =>
    item.estado === "pendiente_revision"
  );
  if (!contribution) {
    if (contributions?.some((item) => item.estado === "aceptada")) {
      return Response.json({ status: "merged" });
    }
    return new Response("No pending contribution found for this user", {
      status: 404,
    });
  }

  const githubToken = Deno.env.get("GITHUB_TOKEN");
  const githubHeaders: Record<string, string> = {
    Accept: "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
  };
  if (githubToken) githubHeaders.Authorization = `Bearer ${githubToken}`;

  const githubResponse = await fetch(
    `https://api.github.com/repos/${encodeURIComponent(contribution.github_owner)}/${encodeURIComponent(contribution.github_repo)}/pulls/${contribution.github_pr_number}`,
    { headers: githubHeaders },
  );
  if (!githubResponse.ok) {
    console.error(
      "GitHub pull request lookup failed:",
      githubResponse.status,
    );
    return new Response(
      githubResponse.status === 404
        ? "Pull request not found or private repository requires GITHUB_TOKEN"
        : "GitHub pull request lookup failed",
      { status: 502 },
    );
  }

  const pullRequest = await githubResponse.json() as {
    state?: string;
    merged_at?: string | null;
  };
  const merged = Boolean(pullRequest.merged_at);
  if (pullRequest.state !== "closed") {
    return Response.json({ status: "open" });
  }

  const { data, error } = await adminClient.rpc("complete_merged_pr", {
    p_github_owner: contribution.github_owner,
    p_github_repo: contribution.github_repo,
    p_github_pr_number: contribution.github_pr_number,
    p_merged: merged,
  });
  if (error) {
    console.error("Could not update contribution:", error.message);
    return new Response("Could not update contribution", { status: 500 });
  }
  return Response.json({ status: merged ? "merged" : "closed", result: data });
});
