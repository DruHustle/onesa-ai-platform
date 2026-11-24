# Agent design

Planner accepts a goal and returns bounded ToolCall proposals. BasicPlanner is the
CPU mock; ModelToolPlanner uses the central ModelClient with registered argument schemas.
Explicit caller-supplied steps bypass planning. Plans are capped at 8 calls/16k output
characters and the configured generation deadline; permissions remain caller/server
allowlist intersection, independent of model text.

Authentication, request validation and explicit tool-permission checks precede
shared model admission. Invalid permissions return 403 without reserving generation
capacity. Valid explicit and model-planned runs use the same concurrency, rate,
token-reservation and expiry limits. Their route releases admission in `finally`,
including planning/execution failure or cancellation, and rechecks session/lease
authority before returning a result. A lost session or lease cannot expose tool output.

ToolRegistry validates arguments with each tool's Pydantic model, then runs a coroutine
with a two-second deadline. Current tools include arithmetic (finite bounded numbers;
no expression eval), text statistics and `knowledge_search`, which revalidates the
active session and retrieves only caller-owned Knowledge documents. Optional Industrial
and Cybersecurity evidence tools remain behind their existing server-side feature gates.
There are zero automatic retries. Tool execution retains the ten-second global deadline,
cooperative cancellation between calls and durable owned run/final-step history.
A caller-supplied run UUID permits concurrent cancel requests; HTTP disconnect is
checked between steps. Stale unfinished runs fail on inspection after a conservative
five-minute bound covering permitted model planning/reporting deadlines.

The signed-in **Chat** tab retains its bounded SSE conversation/history workflow.
The **Work** tab passes an explicit per-run tool allowlist to the existing agent endpoint;
only registered tools may be invoked. The backend model plans at most eight calls when
no explicit steps are supplied. For real inference, successful model-planned runs may
append a bounded AI-generated `work_report` derived from saved tool evidence.
The report is not a new tool grant, is not an external-action receipt, and never
executes additional tool calls. Unavailable reports leave tool results intact.
Mock inference is plainly labeled and does not generate an AI report.

The **Plugins** tab discovers the authenticated `/api/v1/agents/tools` catalog,
using server-registered schemas and effect labels; users consent to available tools
individually each time they run Work. This enables built-in plugins, not arbitrary
end-user installation of remote extensions. Remote account OAuth, third-party MCP
installation, durable background jobs, multi-agent delegation, shell/browser actions,
write-capable tools and action-specific approval gates are not yet implemented.
Adding an effectful tool requires explicit scopes, human confirmation, revocation,
auditability, bounded execution and dedicated security/acceptance tests.
