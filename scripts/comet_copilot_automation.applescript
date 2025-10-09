-- Comet + GitHub Copilot automation
-- Usage (via osascript):
--   osascript scripts/comet_copilot_automation.applescript "<prompt>" "Github Copilot" 30 "<optional_webhook_url>"

-- Revised run: ignore argv; use prompt/flags files under ~/automation
global automationDir, promptFile, responseFile, doneFlag, errorFlag, tabFile

on run
    set homePOSIX to POSIX path of (path to home folder)
    set automationDir to homePOSIX & "automation/"
    set promptFile to automationDir & "copilot_prompt.txt"
    set responseFile to automationDir & "copilot_response.txt"
    set doneFlag to automationDir & "copilot_done.flag"
    set errorFlag to automationDir & "copilot_error.flag"
    set tabFile to automationDir & "copilot_tab.txt"

    try
        do shell script "mkdir -p " & quoted form of automationDir & " ; rm -f " & quoted form of doneFlag & " " & quoted form of errorFlag & " " & quoted form of responseFile

        set promptText to my readTextFile(promptFile)
        if promptText is "" then error "Prompt file is empty: " & promptFile number -1703

        set targetTab to "Github Copilot"
        try
            set maybeTab to my readTextFile(tabFile)
            if (maybeTab as text) is not "" then set targetTab to (maybeTab as text)
        end try

        my focusCometTab(targetTab)
        my injectPromptAndSubmit(promptText)
        delay 0.2
        tell application "System Events"
            tell process "Comet"
                keystroke "a" using {command down}
                keystroke "c" using {command down}
            end tell
        end tell
        set theResponse to (the clipboard as text)
        my writeTextFile(responseFile, theResponse)
        do shell script "printf '%s' " & quoted form of ("ok " & (do shell script "date -u +%FT%TZ")) & " > " & quoted form of doneFlag
    on error errMsg number errNum
        my writeTextFile(errorFlag, "Error " & errNum & ": " & errMsg)
    end try
end run

-- helpers
on readTextFile(p)
    try
        set f to POSIX file p
        set h to open for access f
        set t to read h as «class utf8»
        close access h
        return t
    on error e number n
        try
            close access p
        end try
        error "Cannot read file: " & p & " (" & e & ")" number n
    end try
end readTextFile

on writeTextFile(p, t)
    set f to POSIX file p
    set h to open for access f with write permission
    set eof of h to 0
    write t to h as «class utf8»
    close access h
end writeTextFile

on focusCometTab(tabName)
    tell application "Comet" to activate
    tell application "System Events"
        if not (exists process "Comet") then error "Comet not running" number -128
        tell process "Comet"
            set frontmost to true
            delay 0.2
            set win to front window
            set tabElems to {}
            try
                set tabElems to (every UI element of win whose role description contains "tab")
            end try
            if (count of tabElems) is 0 then
                try
                    set tabElems to (every button of win whose role description contains "tab")
                end try
            end if
            if (count of tabElems) > 0 then
                repeat with te in tabElems
                    try
                        if (name of te as text) is equal to tabName then
                            click te
                            exit repeat
                        end if
                    end try
                end repeat
            end if
        end tell
    end tell
end focusCometTab

on injectPromptAndSubmit(promptText)
    tell application "System Events"
        tell process "Comet"
            set frontmost to true
            set win to front window
            set targetTextArea to missing value
            try
                set targetTextArea to first UI element of win whose role is "AXTextArea"
            end try
            if targetTextArea is not missing value then
                try
                    set value of targetTextArea to promptText
                on error
                    set the clipboard to promptText
                    keystroke "a" using {command down}
                    keystroke "v" using {command down}
                end try
            else
                set the clipboard to promptText
                keystroke "a" using {command down}
                keystroke "v" using {command down}
            end if
            key code 36
        end tell
    end tell
end injectPromptAndSubmit

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
                        set isTabLike to ((role description of el as text) contains "tab")
                    on error
                        -- keep default false
                    end try
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
