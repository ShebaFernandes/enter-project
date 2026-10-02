import { execFileSync } from "node:child_process";

/** Fresh one-time URLs using the existing synthetic-only Django command. */
export function localBootstrap(key: string, role = "recruiter") {
  const origin =
    key === "LOCAL_FM12_BOOTSTRAP_URL"
      ? process.env.FM12_AUTH_ORIGIN
      : key === "LOCAL_FM11_BOOTSTRAP_URL"
        ? process.env.FM11_AUTH_ORIGIN
        : key === "LOCAL_FM10_BOOTSTRAP_URL"
          ? process.env.FM10_AUTH_ORIGIN
          : key === "LOCAL_FM9_BOOTSTRAP_URL"
            ? process.env.FM9_AUTH_ORIGIN
            : key === "LOCAL_FM8_BOOTSTRAP_URL"
              ? process.env.FM8_AUTH_ORIGIN
              : key === "LOCAL_FM7_BOOTSTRAP_URL"
                ? process.env.FM7_AUTH_ORIGIN
                : key === "LOCAL_FM6_BOOTSTRAP_URL"
                  ? process.env.FM6_AUTH_ORIGIN
                  : key === "LOCAL_FM5_BOOTSTRAP_URL"
                    ? process.env.FM5_AUTH_ORIGIN
                    : key === "LOCAL_FM4_BOOTSTRAP_URL"
                      ? process.env.FM4_AUTH_ORIGIN
                      : process.env.LOCAL_AUTH_ORIGIN;
  if (!origin) return process.env[key];
  const result = JSON.parse(
    execFileSync(
      ".venv/bin/python",
      ["manage.py", `bootstrap_local_${role}`, "--base-url", origin, "--json"],
      { encoding: "utf8" },
    ),
  ) as { url: string; recruiter_id?: string };
  // Scenarios reuse the approved synthetic actor but must not share its throttle
  // history. This reset is restricted to the dedicated verification database/cache.
  if (process.env.LOCAL_AUTH_RESET_THROTTLE === "1" && result.recruiter_id) {
    execFileSync(".venv/bin/python", [
      "-c",
      [
        "import os, sys, uuid, django",
        "assert 'enter_fm4_verify_' in os.environ['DATABASE_URL']",
        "assert os.environ['VALKEY_URL'] == 'redis://127.0.0.1:6379/11'",
        "django.setup()",
        "from django.core.cache import cache",
        "cache.delete(f'handoff:{uuid.UUID(sys.argv[1])}:127.0.0.1')",
      ].join("; "),
      result.recruiter_id,
    ]);
  }
  return result.url;
}
