# Troubleshooting

## Application unavailable
Inspect docker compose ps. Database readiness and migrations precede API readiness. Preserve volumes during restart.

## Mock response
Fresh installs default to mock. Model configuration and installed weights must be explicitly qualified; changing UI language does not select a model.

## Unauthorized or CSRF rejected
Use the configured application Origin, valid session and matching CSRF header. Reauthenticate after expiry. Never bypass the checks.

## Empty knowledge result
Use owned document IDs and an indexed embedding version. The current lexical baseline is sensitive to terminology.

## Stream interrupted
Treat missing message_end as incomplete. Retry after release of the active generation; partial answers are not saved as successful messages.

## Travel provider unavailable
Live provider integrations are absent. A model itinerary is not verified live inventory.

## Internal portal denied
Only authorized engineering user IDs receive internal access. Contact the local operator; hiding links is not authorization.
