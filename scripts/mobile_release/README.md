# Internal mobile store pipeline

The repository owns `.github/workflows/mobile-internal-release.yml` and its local
`scripts/mobile_release/` implementation. Pull requests run credential-free native
source and release-contract checks. Publication is an explicit `workflow_dispatch`
on **current main**, with the exact reviewed `source_sha`, a deliberately chosen
unused positive `build_number`, and `android`, `ios`, or `both`.

The workflow runs source checks first, then builds, signs, verifies and uploads the
same artifact. Its protected environment is **mobile-internal**, restricted to main.
The committed marketing version and existing app identifiers remain authoritative.
Only the disposable runner checkout receives the supplied native build counter.
Record that counter with the source SHA; the pipeline does not guess a new version
or change the checked-in product version. Existing release, staged acceptance and
hardware gates still apply before dispatch. Internal beta distribution does not
establish public launch or physical-device acceptance.

The `requiredChecks` list in `.github/mobile-release.json` names the product CI
checks that must have completed successfully on that exact main SHA. The workflow
reads GitHub check runs with a read-only token before preparation and again before
upload. Only GitHub Actions results from an independent run qualify; a missing,
queued, skipped, cancelled or failed check blocks publication. The release workflow
cannot qualify itself. If path filters omitted a required product workflow on a
new main commit, run that existing qualification workflow for the exact main
commit and inspect its result before dispatching a release.

Packaging snapshots every tracked source file, including backend code, workflows,
lockfiles, file modes and symlinks. Each native preparation step can record changes
only to its named generated project inputs or explicit version counters. All other
tracked changes, staged changes and unexpected untracked source block signing or
upload. The signed receipt binds the prepared-source snapshot digest as well as
the artifact digest; the previous unconditional dirty-tree exception is absent.

## Existing identity

See `.github/mobile-release.json` for this product's package, Xcode target and app ID.
A mismatched package, version, signing certificate, Apple team or provisioning
profile stops before upload. These are existing identifiers, not a migration.

## Protected inputs

Missing values fail preflight with **names only**. Do not place credentials in Git,
workflow inputs, repository variables, command text, artifacts or logs. Configure
values in this repository's protected `mobile-internal` environment.

| Android secret | Purpose |
| --- | --- |
| `ANDROID_PLAY_UPLOAD_KEYSTORE_BASE64` | Base64 bytes of the existing Google Play upload keystore |
| `ANDROID_PLAY_UPLOAD_STORE_PASSWORD` | Its keystore password |
| `ANDROID_PLAY_UPLOAD_KEY_PASSWORD` | The independently confirmed upload-key password |
| `GOOGLE_PLAY_SERVICE_ACCOUNT_JSON` | Existing service account with access to this Play app |

| Android variable | Purpose |
| --- | --- |
| `ANDROID_PLAY_UPLOAD_ALIAS` | Existing upload-key alias |
| `ANDROID_PLAY_UPLOAD_CERT_SHA256` | SHA-256 fingerprint independently read from Play Console |

The key password is not assumed to equal the store password. An existing direct APK
`android-distribution` key is not automatically the Play upload key. No replacement
key, reset request, certificate or new store record is generated. The unsigned AAB
must have no signer; the signed output must match the pinned upload certificate and
pass strict signature and bundle validation. React Native ARM64 libraries must meet
16 KB load alignment. CI-only Gradle limits are 4 GiB and two workers; normal project
settings are unchanged.

For Capacitor, both the AAB and exported IPA must contain the existing app ID,
the pinned customer API origin, a nonempty bundled index and every JavaScript
entry that index references. Missing or stale assets, a different origin and a
remote WebView URL stop before upload. Expo IPA validation still requires its
nonempty standalone JavaScript bundle.

| Apple secret | Purpose |
| --- | --- |
| `APPLE_DISTRIBUTION_P12_BASE64` | Existing Apple Distribution certificate with its private key |
| `APPLE_DISTRIBUTION_P12_PASSWORD` | Password protecting that P12 |
| `APPLE_PROVISIONING_PROFILE_BASE64` | Existing exact-app App Store distribution profile |
| `APP_STORE_CONNECT_PRIVATE_KEY` | Existing App Store Connect API private key in PEM/P8 form |

| Apple variable | Purpose |
| --- | --- |
| `APPLE_TEAM_ID` | Existing enrolled team identifier |
| `APPLE_DISTRIBUTION_CERT_SHA256` | Independently verified distribution certificate fingerprint |
| `APP_STORE_CONNECT_KEY_ID` | Existing API key identifier |
| `APP_STORE_CONNECT_ISSUER_ID` | Existing API issuer UUID |
| `APP_STORE_CONNECT_APP_ID` | Existing numeric app record ID |
| `APP_STORE_CONNECT_INTERNAL_GROUP_ID` | Existing internal TestFlight group for that app |

The Apple profile must be unexpired, name the exact bundle ID, contain the pinned
certificate, forbid development debugging and have no device/ad-hoc or enterprise
scope. App ID prefixes can differ from team IDs. Manual signing applies only to the
app target; Pods retain their own build configuration. No automatic provisioning,
new certificate issuance or signing-key export occurs. An ephemeral keychain and
profile are removed in `finally`, including handled interruption, and the hosted
runner's temporary release material is removed after artifact retention.

The macOS runner requires Xcode 26+, CocoaPods and its `xcodeproj` Ruby dependency,
and an altool version supporting `--p8-file-path`; missing tooling fails closed.
Only the IPA/AAB and a sanitized source/version/hash receipt are retained for seven
days. Provisioning/keychain files, P12/P8/keystore files, passwords and provider
responses are never added to artifacts.

## Provider behavior and recovery

Google Play requires its existing app record, initial console setup, Play App
Signing/upload certificate and internal track. The helper creates one edit, checks
existing tracks, uploads the hash-bound bundle, changes **only internal**, validates,
and commits with `changesInReviewBehavior=ERROR_IF_IN_REVIEW`. It does not replace
production/closed tracks, cancel another review, retry a failed commit, or fall back
to a public track. A known precommit failure attempts to delete only its owned edit.
A commit with an unknown response stays explicitly unknown for console inspection.

Apple requires approved API access, the existing app and an existing **internal**
TestFlight group. The helper checks the app's bundle ID and group ownership before
upload. It validates/uploads with Apple's CLI, waits up to 30 minutes for the exact
marketing/build version to process, and assigns that build to the verified internal
group. It creates no groups/testers/invitations and makes no public App Review
submission. Apple export-compliance/account-policy requirements may still block
processing or assignment and must be resolved in the owner's account.

A duplicate version or uncertain upload is not an instruction to choose another
counter and retry blindly. Inspect the recorded artifact digest and exact build in
the provider console first. `upload-started-outcome-unknown` is a failure state, not
proof of publication. Preserve the receipt and complete observation before starting
another upload. Store-side processing, tester eligibility and installation are
separate from a successful upload/track commit.

An Apple upload CLI nonzero exit, timeout or handled interruption is explicitly an
unknown provider outcome. Its receipt remains unknown, temporary API-key files are
removed, and the helper makes no second upload attempt. Generic tool failures do
not claim that no upload occurred.

## Verification

Run `python3 -m unittest discover -s scripts/mobile_release -p 'test_*.py'` and
`python3 scripts/mobile_release/release.py contract` at the root. Tests use synthetic
provider fixtures, temporary signing keys and real OpenSSL signature verification;
they never contact stores or use account credentials. The workflow additionally
installs the native package's committed lockfile, runs its tests/typecheck, and
compiles the actual release for the selected platform before signature validation.

The workflow source and credential-free regressions do **not** establish a signed
or store-accepted release. A successful run must supply the signed artifact digest,
provider receipt, processed internal build/track and installed-device acceptance.
Keep payment wallets, physical controllers, carrier services and other product
capabilities under their existing commissioning gates.

References: [Apple upload guidance](https://developer.apple.com/help/app-store-connect/manage-builds/upload-builds/),
[Google edits](https://developers.google.com/android-publisher/edits),
[Google bundle upload](https://developers.google.com/android-publisher/api-ref/rest/v3/edits.bundles/upload),
[Google commit review behavior](https://developers.google.com/android-publisher/api-ref/rest/v3/edits/commit).
