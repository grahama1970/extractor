-- Stay‑Open Copilot runner for Comet (System Events only; Accessibility grant required)
-- Watches ~/automation/copilot_prompt.txt; when it changes, focuses Comet,
-- types the prompt, submits, copies the response, and writes:
--   ~/automation/copilot_response.txt
--   ~/automation/copilot_done.flag (or copilot_error.flag on failure)

global automationDir, promptFile, responseFile, doneFlag, errorFlag, tabFile, stampFile

on run
  set homePOSIX to POSIX path of (path to home folder)
  set automationDir to homePOSIX & "automation/"
  set promptFile to automationDir & "copilot_prompt.txt"
  set responseFile to automationDir & "copilot_response.txt"
  set doneFlag to automationDir & "copilot_done.flag"
  set errorFlag to automationDir & "copilot_error.flag"
  set tabFile to automationDir & "copilot_tab.txt"
  set stampFile to automationDir & "copilot_laststamp.txt"
  try
    do shell script "mkdir -p " & quoted form of automationDir
  end try
  return
end run

on idle
  try
    set mustRun to my promptChanged()
    if mustRun then my processOnce()
  on error errMsg number errNum
    my writeTextFile(errorFlag, "Error " & errNum & ": " & errMsg)
  end try
  return 2 -- seconds
end idle

on promptChanged()
  tell application "System Events"
    if not (exists file promptFile) then return false
    set mdate to modification date of file promptFile
  end tell
  set lastStamp to my readTextFileDefault(stampFile, "")
  set curStamp to (mdate as string)
  if curStamp is not equal to lastStamp then return true
  return false
end promptChanged

on processOnce()
  try
    -- reset flags
    do shell script "rm -f " & quoted form of doneFlag & " " & quoted form of errorFlag

    -- read prompt + tab
    set promptText to my readTextFile(promptFile)
    if promptText is "" then error "Prompt file is empty" number -1703
    set targetTab to "Github Copilot"
    try
      set maybeTab to my readTextFile(tabFile)
      if (maybeTab as text) is not "" then set targetTab to (maybeTab as text)
    end try

    -- focus Comet via System Events only
    tell application "System Events"
      if not (exists process "Comet") then error "Comet not running" number -128
      tell process "Comet"
        set frontmost to true
        delay 0.2
        set win to front window
        -- click a tab whose role description contains "tab" and name matches
        set tabElems to {}
        try
          set tabElems to (every UI element of win whose role description contains "tab")
        end try
        if (count of tabElems) > 0 then
          repeat with te in tabElems
            try
              if (name of te as text) is equal to targetTab then
                click te
                exit repeat
              end if
            end try
          end repeat
        end if
        -- find a text area and inject prompt
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
        key code 36 -- Return
        delay 0.4
        keystroke "a" using {command down}
        keystroke "c" using {command down}
      end tell
    end tell

    -- write response + flags
    set theResponse to (the clipboard as text)
    my writeTextFile(responseFile, theResponse)
    do shell script "printf '%s' ok > " & quoted form of doneFlag
  on error errMsg number errNum
    my writeTextFile(errorFlag, "Error " & errNum & ": " & errMsg)
  end try
  -- update stamp so we don’t re-run needlessly
  tell application "System Events" to set mdate to modification date of file promptFile
  my writeTextFile(stampFile, (mdate as string))
end processOnce

on readTextFile(p)
  set f to POSIX file p
  set h to open for access f
  set t to read h as «class utf8»
  close access h
  return t
end readTextFile

on readTextFileDefault(p, fallback)
  try
    return my readTextFile(p)
  on error
    return fallback
  end try
end readTextFileDefault

on writeTextFile(p, t)
  set f to POSIX file p
  set h to open for access f with write permission
  set eof of h to 0
  write t to h as «class utf8»
  close access h
end writeTextFile

