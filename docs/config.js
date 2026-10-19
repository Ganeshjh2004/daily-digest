export const WORKFLOW_URL = "https://github.com/Ganeshjh2004/daily-digest/actions/workflows/daily-digest.yml";
export const SCHEDULE_UTC_HOUR = 8;
export const USE_EDGE_SAMPLES = false;

export const DATA_PATHS = USE_EDGE_SAMPLES
  ? { digest: "data/sample-edge-digest.json", run: "data/sample-edge-run.json" }
  : { digest: "data/digest.json", run: "data/run.json" };
