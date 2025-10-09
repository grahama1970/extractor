-- Comet + GitHub Copilot automation
-- Usage (via osascript):
--   osascript scripts/comet_copilot_automation.applescript "<prompt>" "Github Copilot" 30 "<optional_webhook_url>"

on run argv
    if (count of argv) < 1 then return "missing prompt"
    set promptText to item 1 of argv
    set tabSub to "Github Copilot"
    if (count of argv) ≥ 2 then set tabSub to item 2 of argv
    set waitSec to 25
    if (count of argv) ≥ 3 then try
        set waitSec to (item 3 of argv) as integer
    end try
    set webhook to ""
    if (count of argv) ≥ 4 then set webhook to item 4 of argv

    tell application "Comet" to activate
    delay 0.3

    tell application "System Events"
        if not (exists process "Comet") then return "Comet not running"
        tell process "Comet"
            set frontmost to true
            delay 0.2

            my focus_tab_by_name(tabSub)
            delay 0.2

            if my paste_into_active(promptText) is false then
                try
                    my paste_into_text_area(window 1, promptText)
                end try
            end if

            -- submit
            key code 36 -- Return

            -- wait for response (best-effort; time-based)
            my wait_seconds(waitSec)

            -- copy response (best-effort): select-all + copy
            keystroke "a" using {command down}
            delay 0.1
            keystroke "c" using {command down}
        end tell
    end tell

    if webhook is not "" then
        try
            set payload to do shell script "python3 - <<'PY'\nimport json,subprocess\nclip = subprocess.check_output(['pbpaste']).decode('utf-8','ignore')\nprint(json.dumps({'text': clip}))\nPY"
            do shell script "curl -sS -X POST -H 'Content-Type: application/json' --data-binary @- " & quoted form of webhook & " <<'JSON'\n" & payload & "\nJSON"
        end try
    end if
end run

on wait_seconds(n)
    try
        delay n
    end try
end wait_seconds

on paste_into_active(txt)
    try
        tell application "System Events" to keystroke "a" using {command down}
        delay 0.05
        set the clipboard to txt
        tell application "System Events" to keystroke "v" using {command down}
        return true
    on error
        return false
    end try
end paste_into_active

on paste_into_text_area(win, txt)
    tell application "System Events"
        try
            set tas to (every text area of win)
        on error
            set tas to {}
        end try
        repeat with ta in tas
            try
                set value of ta to txt
                exit repeat
            end try
        end repeat
    end tell
end paste_into_text_area

on focus_tab_by_name(targetSub)
    tell application "System Events"
        tell process "Comet"
            -- try tab group first
            try
                ignoring case
                    if (exists (tab group 1 of window 1)) then
                        set tabs to (every radio button of tab group 1 of window 1 whose name contains targetSub)
                        if (count of tabs) > 0 then
                            click item 1 of tabs
                            return
                        end if
                    end if
                end ignoring
            end try
            -- try buttons
            try
                ignoring case
                    set btns to (every button of window 1 whose name contains targetSub)
                    if (count of btns) > 0 then
                        click item 1 of btns
                        return
                    end if
                end ignoring
            end try
            -- deep search and fallback cycling
            set hit to my find_element_by_name(window 1, targetSub)
            if hit is not missing value then
                try
                    click hit
                    return
                end try
            end if
            repeat 12 times
                keystroke (ASCII character 29) using {command down, option down}
                delay 0.25
                ignoring case
                    try
                        if (name of window 1) contains targetSub then exit repeat
                    end try
                end ignoring
            end repeat
        end tell
    end tell
end focus_tab_by_name

on find_element_by_name(container, targetStr)
    tell application "System Events"
        set preferred to missing value
        try
            set elems to every UI element of container
        on error
            set elems to {}
        end try
        repeat with el in elems
            try
                set nm to (name of el) as text
            on error
                set nm to ""
            end try
            ignoring case
                if nm contains targetStr then
                    set isTabLike to false
                    try
                        set rd to (role description of el) as text
                    on error
                        set rd to ""
                    end try
                    if rd contains "tab" then set isTabLike to true
                    try
                        if class of el is radio button then set isTabLike to true
                    end try
                    try
                        if class of el is button then set isTabLike to true
                    end try
                    if isTabLike then return el
                    if preferred is missing value then set preferred to el
                end if
            end ignoring
            try
                set childHit to my find_element_by_name(el, targetStr)
                if childHit is not missing value then return childHit
            end try
        end repeat
        return preferred
    end tell
end find_element_by_name

