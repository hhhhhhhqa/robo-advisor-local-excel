on updatePortfolio(taskInput)
    try
        set taskFields to paragraphs of taskInput
        set folderPath to item 1 of taskFields
        set inputPath to item 2 of taskFields
        set outputPath to item 3 of taskFields
        set requestedAction to item 4 of taskFields
        if requestedAction is not "excel-update" and requestedAction is not "excel-recalculate" then error "Unknown action"
        with timeout of 3600 seconds
            set scriptPath to folderPath & "/scripts/launch.sh"
            do shell script "/bin/bash " & quoted form of scriptPath & " " & requestedAction & " --snapshot " & quoted form of inputPath & " --result " & quoted form of outputPath & " 2>&1"
        end timeout
        return "OK"
    on error messageText number errorNumber
        return "ERROR: " & messageText
    end try
end updatePortfolio
