// Mechanical ontology overlay sync only. ChatGPT owns financial/source validation.
// This file does NOT run source research, economic interpretation, or blind ChatGPT replay.
import fs from "node:fs";
import path from "node:path";

const root = process.cwd();
const rebuildRoot = path.join(root, "research/rebuild");
const outputPath = path.join(root, "research/ontology/active-auto-extensions.json");
const readJson = (p) => JSON.parse(fs.readFileSync(p, "utf8"));
const isFile = (p) => fs.existsSync(p) && fs.statSync(p).isFile();
const sortBy = (field) => (a, b) => String(a[field]).localeCompare(String(b[field]), "en");

function fail(message) {
  throw new Error("AUTO_ONTOLOGY_SYNC_FAILED: " + message);
}
function reachedNodes(nodes, edges) {
  const ids = new Set(nodes.map((n) => n.id));
  const adj = new Map();
  for (const edge of edges) {
    const targets = Array.isArray(edge.to) ? edge.to : [edge.to];
    if (!ids.has(edge.from) || targets.some((target) => !ids.has(target))) {
      fail("edge references nonexistent node: " + JSON.stringify(edge));
    }
    if (!adj.has(edge.from)) adj.set(edge.from, []);
    adj.get(edge.from).push(...targets);
  }
  if (!ids.has("case")) fail("case root missing");
  const reachable = new Set(["case"]);
  const queue = ["case"];
  for (let i = 0; i < queue.length; i++) {
    for (const to of adj.get(queue[i]) || []) {
      if (!reachable.has(to)) {
        reachable.add(to);
        queue.push(to);
      }
    }
  }
  return { reachable: reachable.size, total: ids.size };
}

const cases = [];
const nodeTypes = new Map();
const propertyTypes = new Map();
const relationshipTypes = new Map();
const rejected = [];

if (!fs.existsSync(rebuildRoot)) fail("research/rebuild is missing");
for (const dirName of fs.readdirSync(rebuildRoot).sort()) {
  const caseDir = path.join(rebuildRoot, dirName);
  if (!fs.statSync(caseDir).isDirectory()) continue;
  const activeFile = path.join(caseDir, "active.json");
  if (!isFile(activeFile)) continue;
  const active = readJson(activeFile);
  const coverage = active.source_fact_coverage || active.selected_source_fact_recovery || {};
  const requested = coverage.total ?? coverage.examined;
  const observed = coverage.passed ?? coverage.matched;
  const graphName = active.current_reconstruction_input;
  const compareName = active.latest_comparison || active.current_comparison;
  const graphFile = graphName && path.join(caseDir, path.basename(graphName));
  const compareFile = compareName && path.join(caseDir, path.basename(compareName));
  if (!(Number.isInteger(requested) && requested > 0 && observed === requested &&
        typeof graphName === "string" && path.basename(graphName) === graphName &&
        typeof compareName === "string" && path.basename(compareName) === compareName &&
        isFile(graphFile) && isFile(compareFile))) {
    rejected.push({ case_id: dirName, reason: "NO_VALID_SOURCE_FACT_PASS_OR_GRAPH" });
    continue;
  }
  const comparison = readJson(compareFile);
  const matches = comparison.matched ?? comparison.passed;
  const tested = comparison.selected_count ?? comparison.facts_checked;
  if (!(matches === requested && tested === requested && comparison.failed === 0 &&
        Array.isArray(comparison.rows) && comparison.rows.length === requested &&
        comparison.rows.every((row) => row.passed === true))) {
    rejected.push({ case_id: dirName, reason: "COMPARISON_RECORD_NOT_FULLY_PASSING" });
    continue;
  }
  const graph = readJson(graphFile);
  if (!(Array.isArray(graph.nodes) && Array.isArray(graph.edges))) {
    rejected.push({ case_id: dirName, reason: "GRAPH_SCHEMA_MISSING" });
    continue;
  }
  const graphNodes = new Map();
  for (const n of graph.nodes) {
    if (typeof n.id !== "string" || graphNodes.has(n.id)) fail(dirName + " invalid/duplicate node ID");
    const type = n.canonical_type || n.type || n.ontology_type;
    if (!type || type === "SourceDocument" || type === "SourcePassage") {
      fail(dirName + " blind input contains source/unknown node type");
    }
    graphNodes.set(n.id, type);
  }
  const reach = reachedNodes(graph.nodes, graph.edges);
  if (reach.reachable !== reach.total) {
    rejected.push({ case_id: dirName, reason: "CASE_ROOT_NODE_UNREACHABLE", reachable: reach.reachable, total: reach.total });
    continue;
  }
  if (active.root_reachability &&
      (active.root_reachability.unreachable !== 0 ||
       active.root_reachability.financial_nodes !== reach.total)) {
    rejected.push({ case_id: dirName, reason: "ACTIVE_ROOT_ATTESTATION_MISMATCH" });
    continue;
  }
  const mutation = active.relationship_mutations_R7;
  if (mutation && !(mutation.tested > 0 && mutation.tested === mutation.detected)) {
    rejected.push({ case_id: dirName, reason: "RELATIONSHIP_MUTATION_ATTESTATION_FAILED" });
    continue;
  }

  // This gate certifies ONLY the source-registered fact/path test, never a fresh-chat blind pass.
  const caseEvidence = {
    case_id: dirName,
    graph_file: "research/rebuild/" + dirName + "/" + graphName,
    source_comparison_file: "research/rebuild/" + dirName + "/" + compareName,
    passed_registered_facts: requested,
    reached_financial_nodes: reach.reachable,
    total_financial_nodes: reach.total,
    relation_mutation_checks: mutation ? { detected: mutation.detected, tested: mutation.tested } : null,
    auto_adopted_scope: "SOURCE_REGISTERED_FACTS_GRAPH_PATH_PASS",
    independent_chatgpt_blind: "NOT_ATTESTED_BY_THIS_SYNC",
    full_original_reproduction: "NOT_ATTESTED_BY_THIS_SYNC"
  };
  cases.push(caseEvidence);

  const caseId = dirName;
  for (const n of graph.nodes) {
    const nodeType = graphNodes.get(n.id);
    if (!nodeTypes.has(nodeType)) nodeTypes.set(nodeType, { name: nodeType, case_ids: new Set(), example_nodes: new Set() });
    nodeTypes.get(nodeType).case_ids.add(caseId);
    nodeTypes.get(nodeType).example_nodes.add(caseId + ":" + n.id);
    const properties = n.properties || n.fields || {};
    for (const [prop, value] of Object.entries(properties)) {
      const key = nodeType + "." + prop;
      if (!propertyTypes.has(key)) propertyTypes.set(key, {
        owner_type: nodeType, name: prop, case_ids: new Set(), observed_json_types: new Set()
      });
      const record = propertyTypes.get(key);
      record.case_ids.add(caseId);
      record.observed_json_types.add(value === null ? "null" : Array.isArray(value) ? "array" : typeof value);
    }
  }
  for (const e of graph.edges) {
    for (const target of (Array.isArray(e.to) ? e.to : [e.to])) {
      const domain = graphNodes.get(e.from);
      const range = graphNodes.get(target);
      const term = e.relation;
      if (!term || !domain || !range) fail(caseId + " relationship missing typed endpoint");
      const signature = term + "|" + domain + "|" + range;
      if (!relationshipTypes.has(signature)) relationshipTypes.set(signature, {
        name: term, domain, range, case_ids: new Set()
      });
      relationshipTypes.get(signature).case_ids.add(caseId);
    }
  }
}
const byName = (set) => [...set].sort();
const out = {
  schema: "AUTO_ADOPTED_ONTOLOGY_OVERLAY_V1",
  role: "ACTIVE_RESEARCH_ONTOLOGY_OVERLAY_NONDESTRUCTIVE",
  baseline_policy: "Preserve all 604 original occurrence definitions and prior established identifiers; overlay adds/reuses observed graph definitions without overwriting baseline.",
  automatic_rule: "Once all registered source facts match and all graph-only financial nodes are reachable, the successful graph's node classes, owner-qualified property names and typed relationships are adopted in this versioned research overlay without a separate approval job.",
  evidence_limit: "Selected fact reconstruction/path traversal is not an independent new ChatGPT conversation, full original review, or actual trading PnL verification.",
  cases,
  node_types: [...nodeTypes.values()].map((v) => ({
    name: v.name, case_ids: byName(v.case_ids), example_nodes: byName(v.example_nodes).slice(0, 3)
  })).sort(sortBy("name")),
  attribute_types: [...propertyTypes.values()].map((v) => ({
    owner_type: v.owner_type, name: v.name, case_ids: byName(v.case_ids),
    observed_json_types: byName(v.observed_json_types)
  })).sort((a, b) => (a.owner_type + "." + a.name).localeCompare(b.owner_type + "." + b.name, "en")),
  relation_types: [...relationshipTypes.values()].map((v) => ({
    name: v.name, domain: v.domain, range: v.range, case_ids: byName(v.case_ids)
  })).sort((a, b) => (a.name + ":" + a.domain + ":" + a.range).localeCompare(b.name + ":" + b.domain + ":" + b.range, "en")),
  skipped_cases: rejected
};
out.summary = {
  auto_adopted_cases: cases.length, node_type_names: out.node_types.length,
  owner_qualified_attribute_names: out.attribute_types.length,
  typed_relation_signatures: out.relation_types.length,
  distinct_relation_names: new Set(out.relation_types.map((v) => v.name)).size
};
if (!cases.length) fail("No valid passing cases; refusing to replace active overlay");
fs.mkdirSync(path.dirname(outputPath), { recursive: true });
fs.writeFileSync(outputPath, JSON.stringify(out, null, 2) + "\n");
console.log(JSON.stringify({ output: path.relative(root, outputPath), ...out.summary, skipped_cases: rejected }, null, 2));
