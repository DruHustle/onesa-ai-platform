# Onesa AI Platform native applications

This is the iOS and Android React Native project for Onesa AI Platform. It uses
the existing AI service and Onesa account authority. It contains native screens,
not a WebView. The existing product application identifier is `eu.onesa.aiplatform`; the app callback is
`onesaai://auth/callback`. These are source configuration, not evidence that a
store record or signing identity has been registered. The earlier prototype at
`../../mobile` is preserved for its existing development checks; this candidate
and that prototype share the product identifier and cannot be installed side by
side. The protected release workflow selects this reviewed project explicitly.

## Workspace

- Chat creates conversations, streams bounded responses, restores saved history,
  keeps drafts in memory across tabs, and offers Stop with truthful cancellation
  and persistence status. It uses the same versioned SSE parser as the web app.
- Knowledge lists and searches owned documents with source and retrieval metadata.
  Upload, document removal and full older-history browsing remain on the web.
- Agents requires explicit selection and confirmation of the available local
  computation tools. It shows the owned execution history and never adds machine
  control, external messages or bookings.
- Travel creates and reads saved itineraries. Actual provider/mock status and the
  absence of verified prices, availability and bookings remain visible.

The UI follows the device's appearance, supports tablets and retains the approved
AI identity. There is no appearance preference, clock schedule, model download,
paid dependency, remote code update or camera/microphone permission.

## Generate the native projects

Use the repository's Node24 toolchain and this directory's committed lockfile:

```sh
npm ci --ignore-scripts
npm test
npm run typecheck
npm run export
npm run prebuild
node scripts/check-native-projects.mjs
```

Prebuild creates `ios/OnesaAIPlatform.xcodeproj` and the `android/` Gradle project.
These reproducible generated directories are ignored; `app.json`, the lockfile,
Expo plugins and native source are the reviewed inputs. There are no hand edits
inside generated projects. On a Mac run `pod install --project-directory=ios`,
then open `ios/OnesaAIPlatform.xcworkspace`. `npm run ios` and `npm run android`
compile and launch the corresponding development app. Use an installed build
for sign-in; Expo Go does not own this project's callback scheme.

`.github/workflows/native-projects.yml` validates source/bundles and compiles a
credential-free Android debug application and unsigned iOS simulator application.
Internal store releases use the separate protected mobile release workflow.
Neither an export nor unsigned compilation is store signing or device acceptance.

## Sign-in and release boundary

The app starts a short-lived S256 PKCE request at the fixed canonical
`https://platform.onesa.eu` origin. The system browser handles existing Onesa
sign-in and explicit native consent. Only a one-use code and state return through
the exact app callback; the PKCE verifier stays in memory. The native access token
is stored in device secure storage and is never placed in URLs, ordinary storage,
logs, model requests or source files. A cold-start callback cannot redeem a lost
in-memory flow. Cancelling sign-in leaves the app signed out.

All native API requests omit cookies, use `Origin: onesaai://native` and reject
redirects. A fixed route allowlist excludes account administration and industrial
control. The server remains authoritative for account access, object ownership,
expiry and central/local revocation. Sign-out revokes this native session; other
Onesa sessions are not globally signed out. An unconfirmed network outcome is
reported honestly and is never automatically resubmitted.

The additive native server bridge is disabled by default. A reviewed migration,
existing owner-controlled backend/frontend qualification and explicit activation
are required before production native sign-in works. Missing support produces an
unavailable state and a fixed link to the existing web workspace. No credentials,
service activation, store acceptance, physical-device test, model-language result
or production deployment is implied by this source project.

## Verification scope

The local suite tests callback/PKCE bindings, fixed destinations, cookie exclusion,
uncertain-write nonretry, session expiry, response limits, account switches after
headers, stream termination/UTF-8 and native configuration. Hosted and installed
device acceptance must additionally cover system-browser cold/remembered sign-in,
cancel, account switching, secure storage, logout/revocation, backgrounding,
VoiceOver/TalkBack and the four authenticated workspace journeys.

The source identity and native build identity must match the existing release
receipt. Follow the repository's dev → staging → main process; do not activate
the bridge or sign/upload a build from a feature branch.
