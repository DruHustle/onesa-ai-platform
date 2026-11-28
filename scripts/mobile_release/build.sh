#!/usr/bin/env bash
# No signing/provider credentials belong in this dependency/build process.
set -euo pipefail
root=$(cd "$(dirname "$0")/../.." && pwd)
cd "$root"
action=${1:?Use quality, prepare, or android}
platform=${2:-}
work=${3:-}
field() { python3 -c 'import json,sys; print(json.load(open(".github/mobile-release.json"))[sys.argv[1]])' "$1"; }
mobile="$root/$(field mobilePath)"
framework=$(field framework)
export CI=1 EXPO_NO_TELEMETRY=1 PYTHONDONTWRITEBYTECODE=1
checkpoint() { (cd "$root" && python3 scripts/mobile_release/release.py checkpoint --platform "$platform" --work "$work" --stage "${1:-verify}"); }

case "$action" in
  quality)
    python3 -m unittest discover -s scripts/mobile_release -p 'test_*.py'
    python3 scripts/mobile_release/release.py contract
    cd "$mobile"
    npm ci --no-audit --no-fund
    npm test
    if node -e 'process.exit(require("./package.json").scripts.typecheck ? 0 : 1)'; then npm run typecheck; fi
    if [[ "$framework" == capacitor ]]; then npm run build; fi
    ;;
  prepare)
    test -n "$work" && test -n "${RELEASE_BUILD_NUMBER:-}"
    python3 scripts/mobile_release/release.py context --work "$work" --build-number "$RELEASE_BUILD_NUMBER"
    cd "$mobile"
    npm ci --no-audit --no-fund
    checkpoint
    if [[ "$framework" == capacitor ]]; then
      npm run build
      checkpoint
      npx --no-install cap sync "$platform"
      checkpoint native-sync
    elif [[ "$(cd "$root" && field generatedNative)" == True ]]; then
      if [[ "$(cd "$root" && field repository)" == DruHustle/onesa-drone ]]; then
        cd "$root"
        python3 -m scripts.mobile_native_compile prepare --platform "$platform" --output "$work/prepared"
      else
        npx --no-install expo prebuild --platform "$platform" --no-install --template ./node_modules/expo/template.tgz
      fi
      checkpoint native-sync
    fi
    cd "$root"
    python3 scripts/mobile_release/release.py stamp --platform "$platform" --work "$work"
    if [[ "$platform" == ios ]]; then
      cd "$mobile"
      if [[ -f ios/Podfile ]]; then
        pod install --project-directory=ios
        checkpoint pods
      fi
      # The app-target signing editor uses the same xcodeproj dependency as CocoaPods.
      ruby -rxcodeproj -e 'abort "xcodeproj missing" unless defined?(Xcodeproj::Project)'
      if [[ "$framework" == expo ]]; then
        node_bin=$(command -v node)
        printf 'export NODE_BINARY=%q\n' "$node_bin" > ios/.xcode.env.local
      fi
    fi
    if [[ -f "$root/scripts/check-store-policies.sh" ]]; then bash "$root/scripts/check-store-policies.sh"; fi
    checkpoint
    ;;
  android)
    test -n "$work"
    checkpoint
    mkdir -p "$work"
    # Expo templates may contain a debug signing stanza. Disable it for the
    # generated release task and independently reject any signed input later.
    cat > "$work/unsigned.gradle" <<'GRADLE'
gradle.projectsEvaluated {
  def app = rootProject.findProject(':app')
  if (app == null || !app.plugins.hasPlugin('com.android.application')) {
    throw new GradleException('Expected one Android app project')
  }
  app.android.buildTypes.release.signingConfig = null
}
GRADLE
    cd "$mobile"
    bash android/gradlew -p android --no-daemon --max-workers=2 --no-parallel \
      -Dorg.gradle.jvmargs=-Xmx4g --init-script "$work/unsigned.gradle" \
      -PreactNativeArchitectures=arm64-v8a,x86_64 :app:bundleRelease
    checkpoint
    ;;
  *) echo 'Use quality, prepare, or android.' >&2; exit 2 ;;
esac
