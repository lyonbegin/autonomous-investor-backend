#!/usr/bin/env bash
set -euo pipefail
mkdir -p reports/ai-invest-mts-emulator
REPORT=reports/ai-invest-mts-emulator
APK=android/ai-invest-mts/app/build/outputs/apk/debug/app-debug.apk
adb wait-for-device
adb devices -l > "$REPORT/adb-devices.txt"
adb shell getprop ro.build.version.release > "$REPORT/android-version.txt"
adb install -r "$APK" | tee "$REPORT/install.txt"
adb logcat -c
adb shell am start -W -n com.lyonbegin.aiinvestmts/.MainActivity | tee "$REPORT/launch.txt"
sleep 4
capture() {
  local label="$1"; local attempt=0
  while ! adb shell uiautomator dump /sdcard/window.xml > /dev/null 2>&1; do
    attempt=$((attempt+1)); if ((attempt>=3)); then echo "UI_DUMP_FAILED"; return 1; fi; sleep 1
  done
  adb pull /sdcard/window.xml "$REPORT/$label.xml" > /dev/null
  adb shell screencap -p /sdcard/current.png
  adb pull /sdcard/current.png "$REPORT/$label.png" > /dev/null
}
check_text() {
 python3 - "$REPORT/$1.xml" "$2" <<'PY'
import sys,xml.etree.ElementTree as ET
root=ET.parse(sys.argv[1]).getroot()
vals=[v.attrib.get('text','') for v in root.iter('node')]
assert any(sys.argv[2] in v for v in vals),(sys.argv[2],vals)
print('UI_TEXT_PASS',sys.argv[2])
PY
}
tap_text() {
 local match="$1"
 capture before_tap
 local coord
 coord="$(python3 - "$REPORT/before_tap.xml" "$match" <<'PY'
import sys,re,xml.etree.ElementTree as ET
root=ET.parse(sys.argv[1]).getroot()
node=next((n for n in root.iter('node') if n.attrib.get('text','')==sys.argv[2]),None)
assert node is not None,sys.argv[2]
a=list(map(int,re.findall(r'\d+',node.attrib['bounds'])))
print((a[0]+a[2])//2,(a[1]+a[3])//2)
PY
)"
 adb shell input tap $coord
 sleep 2
}
capture home
check_text home 'AI 투자 스튜디오'
check_text home '오늘의 투자'
tap_text '발견'
capture discover
check_text discover '종목 검색'
tap_text '삼성전자'
capture stock
check_text stock '관심종목 등록'
tap_text '관심종목 등록'
capture watch-added
check_text watch-added '관심종목 해제'
tap_text 'AI 상담'
capture agents
check_text agents '전문 AI 선택'
tap_text '반도체 분석 AI'
capture chat
check_text chat '질문 기록'
adb logcat -d -v time > "$REPORT/logcat.txt"
if grep -E 'FATAL EXCEPTION|Process: com.lyonbegin.aiinvestmts.*has died' "$REPORT/logcat.txt" > "$REPORT/fatal-errors.txt"; then echo 'APP_CRASH' ; exit 1; fi
echo 'ANDROID_EMULATOR_ACTUAL_PASS: home, discovery, detail, watchlist, agents, chat' > "$REPORT/RESULT.txt"
cat "$REPORT/RESULT.txt"
