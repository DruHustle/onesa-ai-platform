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
with a two-second deadline. Current tools are arithmetic (finite bounded numbers; no
expression eval) and text statistics. There are zero automatic retries. Execution has a
10-second global deadline, cooperative cancellation between calls, and durable owned
run/final-step history. A caller-supplied run UUID permits concurrent cancel requests;
HTTP disconnect is checked between steps. Stale unfinished runs fail on inspection.

External effects, network tools, general autonomous planning, durable job queues and
approval UI are not shipped capabilities. Adding an effectful tool requires separate
permission/confirmation contracts and tests; model output cannot authorize it.
