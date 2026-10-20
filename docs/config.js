export const WORKFLOW_URL = "https://github.com/Ganeshjh2004/daily-digest/actions/workflows/daily-digest.yml";
export const SCHEDULE_UTC_HOUR = 8;
export const USE_EDGE_SAMPLES = false;

export const DATA_PATHS = USE_EDGE_SAMPLES
  ? { digest: "data/sample-edge-digest.json", run: "data/sample-edge-run.json" }
  : { digest: "data/digest.json", run: "data/run.json" };

// GitHub API constants for the owner-mode "Run Digest Now" dispatch.
// These are public identifiers (no secrets). The token is supplied at runtime
// by the owner and stored only in sessionStorage.
export const GITHUB_OWNER = "Ganeshjh2004";
export const GITHUB_REPO = "daily-digest";
export const WORKFLOW_FILE = "daily-digest.yml";
export const REF = "main";
