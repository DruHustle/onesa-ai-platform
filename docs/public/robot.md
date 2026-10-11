# Robot software simulation

## Implemented release scope

Onesa AI Robot currently implements an authenticated software simulator. The repository's actual directories are `onesa-ai-robot-frontend` and `onesa-ai-robot-backend`. The static interface uses a Node same-origin API proxy; the backend is FastAPI with private SQLite state. The interface indicates connection state, synthetic joint position, proposals, approvals, cancellation, stop state and action history. Telemetry is simulated, not measured hardware.

Operators authenticate, explicitly reset the simulation stop, propose a movement and separately confirm approval. Proposals expire after 15 seconds. An independent gate checks freshness, position, velocity and acceleration when proposing, approving and stepping the simulation. Connection loss, watchdog expiry, revocation, shutdown and restart remove execution authority. The simulator never automatically resumes a command after restart.

## Safety boundary

The joint and limits are synthetic and do not certify physical hardware. Physical actuation is disabled; attempting to enable it rejects startup. Model-generated actions cannot be connected directly to actuators. Physical emergency stops, sensors, controllers, independent validation and hardware-specific approval remain unavailable and outside the software simulation verdict.

## ROS 2, audio, vision and VLA

The ROS 2 package contains preparatory message definitions for simulation telemetry and proposals. It is not a running ROS node, hardware bridge or validated action server. STT, VLM, TTS and VLA interfaces are architectural proposals. There is no live robot camera or real perception model in this release. Robot-to-AI API integration is proposed and must remain authorized and versioned; no shared private database access is allowed.

## Persistence and hosting

SQLite must be private, on persistent storage and managed by one process. Database operations share the application's event-loop thread. Backup uses an online SQLite snapshot, not copying only an active WAL database file. A free ephemeral Render filesystem cannot qualify durable robot task history. The public robot domain currently serves an earlier preview; source tests do not qualify a hosted simulator.

[Open Robot interface](https://robot.onesa.eu/) · [Ecosystem](ecosystem.md) · [Safety overview](security-overview.md). Do not use the interface as evidence of physical hardware readiness.
