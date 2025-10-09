#!/usr/bin/env bash
set -euo pipefail

APP_PATH=${1:-}
BUNDLE_ID=${2:-com.extractor.CopilotRunner}
APP_NAME=${3:-CopilotRunner}

if [[ -z "${APP_PATH}" || ! -d "${APP_PATH}" ]]; then
  echo "Usage: $0 /path/to/CopilotRunner.app [bundle.id] [AppName]" >&2
  exit 2
fi

INFO_PLIST="${APP_PATH}/Contents/Info.plist"
PLISTBUDDY="/usr/libexec/PlistBuddy"
LSREGISTER="/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister"

echo "[*] Patching Info.plist at ${INFO_PLIST}"
if ! "${PLISTBUDDY}" -c "Print :CFBundleIdentifier" "${INFO_PLIST}" >/dev/null 2>&1; then
  "${PLISTBUDDY}" -c "Add :CFBundleIdentifier string ${BUNDLE_ID}" "${INFO_PLIST}"
else
  "${PLISTBUDDY}" -c "Set :CFBundleIdentifier ${BUNDLE_ID}" "${INFO_PLIST}"
fi

if ! "${PLISTBUDDY}" -c "Print :CFBundleName" "${INFO_PLIST}" >/dev/null 2>&1; then
  "${PLISTBUDDY}" -c "Add :CFBundleName string ${APP_NAME}" "${INFO_PLIST}"
else
  "${PLISTBUDDY}" -c "Set :CFBundleName ${APP_NAME}" "${INFO_PLIST}"
fi

if ! "${PLISTBUDDY}" -c "Print :CFBundleDisplayName" "${INFO_PLIST}" >/dev/null 2>&1; then
  "${PLISTBUDDY}" -c "Add :CFBundleDisplayName string ${APP_NAME}" "${INFO_PLIST}"
else
  "${PLISTBUDDY}" -c "Set :CFBundleDisplayName ${APP_NAME}" "${INFO_PLIST}"
fi

echo "[*] Re-registering with LaunchServices"
"${LSREGISTER}" -f "${APP_PATH}"

echo "[*] Re-signing ad-hoc (required after Info.plist change)"
codesign --force --deep --sign - "${APP_PATH}"

echo "[*] Done. Launch via: open -b ${BUNDLE_ID}"

