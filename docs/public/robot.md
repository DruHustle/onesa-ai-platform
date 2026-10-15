# Onesa AI Robot

**Under development.** Onesa AI Robot explores intelligent interaction with the physical world. Hardware, controller integration and perception capabilities are still being developed.

## Protected development workspace

Authorized users can access the operator workspace for controlled software development and testing. It supports reviewing simulation state, proposing an action, confirming it separately, stopping the simulation and reviewing private action history. Simulation values describe a software example; they are not measurements from connected hardware.

Proposals expire and must pass independent validation. A lost connection, expired authority or a stop prevents continued execution. Reopening the workspace does not automatically resume an action.

## Administrator control and hardware readiness

The software is being developed with administrator control over whether physical operation is permitted. Permission and a connected, validated controller are separate requirements. An administrator's permission does not establish that a robot is connected or ready to move. The current development simulator does not demonstrate physical actuation.

Future hardware operation requires the intended controller, independent safety checks and the relevant hardware-specific validation. Model suggestions cannot bypass these controls.

## Explore the product

[Onesa AI Robot](https://robot.onesa.eu/) presents the product and its development direction. The [operator workspace](https://robot.onesa.eu/console) requires authorized access. Concept artwork and software simulation illustrate development possibilities rather than deployed hardware capabilities.

See the [Onesa ecosystem](ecosystem.md), [AI Platform](ai-platform.md) and [security and authorization overview](security-overview.md). Detailed implementation and operating procedures are restricted to authorized engineering documentation.
