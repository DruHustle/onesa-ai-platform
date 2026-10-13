# Robot technical design

## Implemented processes

The actual frontend is onesa-ai-robot-frontend, not an assumed interface directory. Static HTML/JavaScript and Node same-origin routing communicate with robot_api/main.py. FastAPI validates operator sessions and independent safety constraints. The local SQLite profile owns sessions, tasks and stop state; event-loop thread ownership prevents concurrent implicit transactions. The implemented staging-only Turso profile keeps local sessions and safety in process memory and persists bounded task history plus an exclusive owner lease remotely. There is one configured operator, not an implemented multi-role hierarchy.

## Command lifecycle

An authenticated operator resets the simulated stop, proposes bounded motion and separately approves before the 15-second proposal deadline. SafetyGate verifies position, velocity, acceleration and freshness independently on proposal, approval and execution. Stop, cancellation, watchdog expiry, lost connection and revocation remove authority. Restart clears sessions, cancels unfinished tasks and starts stopped. No automatic replay/resume is permitted.

## Persistence and recovery

Use a private persistent database path and one process. SQLite online backup must capture a consistent WAL-aware state. Verify checksums, owner permissions, task history and stopped/revoked restart state in isolated restore acceptance. Free ephemeral Render service storage does not meet this production persistence gate. Turso journal source and separate staging identity are implemented; rolling replacement must safely release the existing live-owner lease before the new owner acquires it. The reviewed staging handoff is not yet hosted-qualified; it does not reset the operator password, delete history, bypass login or authorize physical action.

## Planned boundaries

ROS 2 message files define simulation telemetry/proposals only. Isolated Jazzy CI compiles the SimulationTelemetry and SimulationProposal message definitions and tests synthetic local messaging. No integrated cloud-to-edge ROS node, camera, STT/VLM/TTS, VLA policy, controller or actuator driver is established. ROS services and actions for robot execution are not implemented. Proposed AI integration cannot query private Portal/AI tables and cannot bypass independent validation. Physical actuation settings must continue to reject startup. Hardware safety qualification, package ownership/licensing and real sensor/controller tests remain separate approvals.
