Attribute VB_Name = "Module1"
Option Explicit

Private pendingTime As Date
Private isRunning As Boolean
Private needsCalculation As Boolean

Private Function QualifiedMacro(ByVal macroName As String) As String
    QualifiedMacro = "'" & Replace(ThisWorkbook.Name, "'", "''") & "'!" & macroName
End Function

Private Function LocalPath(ByVal child As String) As String
#If Mac Then
    LocalPath = ThisWorkbook.Path & "/" & child
#Else
    LocalPath = ThisWorkbook.Path & "\" & Replace(child, "/", "\")
#End If
End Function

Public Sub Auto_Open()
    On Error Resume Next
    EnsureUpdateButton
    QueueCalculation
End Sub

Public Sub EnsureUpdateButton()
    Dim ws As Worksheet, button As Shape
    Set ws = ThisWorkbook.Worksheets("Dashboard")
    On Error Resume Next
    Set button = ws.Shapes("UpdatePortfolioButton")
    On Error GoTo 0
    If button Is Nothing Then
        Set button = ws.Shapes.AddShape(5, ws.Range("H3").Left, ws.Range("H3").Top, 180, 29)
        button.Name = "UpdatePortfolioButton"
    End If
    With button
        .OnAction = QualifiedMacro("UpdatePortfolio")
        .Fill.ForeColor.RGB = RGB(23, 50, 77)
        .Line.Visible = False
        .TextFrame.Characters.Text = "Update"
        .TextFrame.Characters.Font.Name = "Arial"
        .TextFrame.Characters.Font.Size = 11
        .TextFrame.Characters.Font.Bold = True
        .TextFrame.Characters.Font.Color = RGB(255, 255, 255)
        .TextFrame.HorizontalAlignment = xlHAlignCenter
        .TextFrame.VerticalAlignment = xlVAlignCenter
    End With
End Sub

Public Sub CancelPendingCalculation()
    On Error Resume Next
    If pendingTime <> 0 Then Application.OnTime pendingTime, QualifiedMacro("RecalculatePortfolio"), , False
    pendingTime = 0
End Sub

Public Sub QueueCalculation()
    If isRunning Then Exit Sub
    needsCalculation = True
    CancelPendingCalculation
    ThisWorkbook.Worksheets("Dashboard").Range("H1").Value = "Inputs changed. Calculating from local data..."
    pendingTime = Now + TimeSerial(0, 0, 2)
    Application.OnTime pendingTime, QualifiedMacro("RecalculatePortfolio")
End Sub

Public Sub RecalculatePortfolio()
    CancelPendingCalculation
    If isRunning Then Exit Sub
    'Never switch away from another workbook for an automatic calculation.
    If Not (Application.ActiveWorkbook Is ThisWorkbook) Then
        Exit Sub
    End If
    RunPortfolio False
End Sub

Public Sub ResumePendingCalculation()
    If needsCalculation And Not isRunning Then QueueCalculation
End Sub

Public Sub UpdatePortfolio()
    CancelPendingCalculation
    If Not isRunning Then RunPortfolio True
End Sub

Public Sub RefreshSelectedDate()
    Dim chart As ChartObject
    ThisWorkbook.Worksheets("Dashboard").Calculate
    For Each chart In ThisWorkbook.Worksheets("Dashboard").ChartObjects
        chart.Chart.Refresh
    Next chart
End Sub

Private Function ErrorDetail(ByVal errorPath As String) As String
    Dim fileNumber As Integer, lineText As String
    On Error GoTo Done
    If Dir(errorPath) = "" Then Exit Function
    fileNumber = FreeFile
    Open errorPath For Input As #fileNumber
    Do Until EOF(fileNumber)
        Line Input #fileNumber, lineText
        ErrorDetail = ErrorDetail & lineText & " "
    Loop
Done:
    On Error Resume Next
    If fileNumber > 0 Then Close #fileNumber
End Function

Private Sub RunPortfolio(ByVal refreshMarket As Boolean)
    Dim resultBook As Workbook, oldSheet As Worksheet, newSheet As Worksheet
    Dim inputPath As String, resultPath As String, tempFolder As String, separator As String
    Dim action As String, status As String, command As String, taskInput As String
    Dim exitCode As Long, oldEvents As Boolean, oldAlerts As Boolean, oldScreen As Boolean
    Dim failure As String, originalSelection As String, savedRow As Long, savedColumn As Long
    Dim oldRenamed As Boolean, imported As Boolean
    Dim control As Shape, chart As ChartObject, lastRow As Long, links As Variant, link As Variant
    isRunning = True
    needsCalculation = False
    oldEvents = Application.EnableEvents
    oldAlerts = Application.DisplayAlerts
    oldScreen = Application.ScreenUpdating
    On Error GoTo Failed
    Set oldSheet = ThisWorkbook.Worksheets("Dashboard")
    If ThisWorkbook.ReadOnly Then Err.Raise 1001, , "Open a writable local copy."
    If Len(ThisWorkbook.Path) = 0 Then Err.Raise 1002, , "Save this workbook in the downloaded tool folder."
    If refreshMarket Then action = "excel-update" Else action = "excel-recalculate"
    If TypeName(Selection) = "Range" Then originalSelection = Selection.Address
    savedRow = ActiveWindow.ScrollRow
    savedColumn = ActiveWindow.ScrollColumn
#If Mac Then
    tempFolder = Environ$("TMPDIR")
    separator = "/"
#Else
    tempFolder = Environ$("TEMP")
    separator = "\"
#End If
    If Len(tempFolder) = 0 Then Err.Raise 1003, , "No temporary folder. Restart Excel and try again."
    If Right$(tempFolder, 1) <> separator Then tempFolder = tempFolder & separator
    tempFolder = tempFolder & "RoboAdvisor-" & Format(Now, "yyyymmddhhnnss") & "-" & CStr(CLng(Timer * 1000))
    MkDir tempFolder
    inputPath = tempFolder & separator & "input.xlsm"
    resultPath = tempFolder & separator & "result.xlsx"
    Application.EnableEvents = False
    Application.ScreenUpdating = False
    If refreshMarket Then
        oldSheet.Range("H1").Value = "Updating asset prices and FX rates..."
    Else
        oldSheet.Range("H1").Value = "Calculating from local data. No API requests."
    End If
    'SaveCopyAs includes unsaved edits without changing the open workbook's path.
    ThisWorkbook.SaveCopyAs inputPath
#If Mac Then
    taskInput = ThisWorkbook.Path & vbLf & inputPath & vbLf & resultPath & vbLf & action
    status = AppleScriptTask("RoboAdvisorExcel_v2.applescript", "updatePortfolio", taskInput)
    If Left$(status, 2) <> "OK" Then Err.Raise 1004, , status
#Else
    command = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File " & Chr(34) & LocalPath("scripts/launch.ps1") & Chr(34)
    command = command & " -Action " & action & " -Snapshot " & Chr(34) & inputPath & Chr(34) & " -Result " & Chr(34) & resultPath & Chr(34)
    exitCode = CreateObject("WScript.Shell").Run(command, 0, True)
    If exitCode <> 0 Then
        failure = ErrorDetail(tempFolder & separator & "result.error.txt")
        If Len(failure) = 0 Then failure = "Run 1_Setup first, or see local_data/last_update.log."
        Err.Raise 1005, , failure
    End If
#End If
    If Dir(resultPath) = "" Then Err.Raise 1006, , "No result returned. See local_data/last_update.log."
    Set resultBook = Workbooks.Open(Filename:=resultPath, UpdateLinks:=0, ReadOnly:=True)
    resultBook.Worksheets("Dashboard").Name = "IncomingResult"
    On Error Resume Next
    resultBook.Names("MonitorDates").Delete
    On Error GoTo Failed
    'Keep the input sheet until the complete replacement is ready.
    resultBook.Worksheets("IncomingResult").Copy After:=oldSheet
    Set newSheet = ThisWorkbook.Worksheets(oldSheet.Index + 1)
    imported = True
    oldSheet.Name = "PreviousDashboard"
    oldRenamed = True
    newSheet.Name = "Dashboard"
    EnsureUpdateButton
    lastRow = 439 + CLng(newSheet.Range("F8").Value)
    'Excel can keep a copied chart/control linked to the temporary source book.
    For Each chart In newSheet.ChartObjects
        With chart.Chart
            .SeriesCollection(1).Name = "Portfolio value USD"
            .SeriesCollection(2).Name = "Selected value USD"
            .SeriesCollection(1).Values = newSheet.Range("B440:B" & lastRow)
            .SeriesCollection(1).XValues = newSheet.Range("A440:A" & lastRow)
            .SeriesCollection(2).Values = newSheet.Range("I440:I" & lastRow)
            .SeriesCollection(2).XValues = newSheet.Range("A440:A" & lastRow)
        End With
    Next chart
    For Each control In newSheet.Shapes
        If control.Type = msoFormControl Then
            If control.FormControlType = xlScrollBar Then
                control.ControlFormat.LinkedCell = "'Dashboard'!$F$8"
                control.OnAction = QualifiedMacro("RefreshSelectedDate")
            End If
        End If
    Next control
    On Error Resume Next
    ThisWorkbook.Names("MonitorDates").Delete
    On Error GoTo Failed
    ThisWorkbook.Names.Add Name:="MonitorDates", RefersTo:="='Dashboard'!$A$440:$A$" & lastRow
    links = ThisWorkbook.LinkSources(xlExcelLinks)
    If IsArray(links) Then
        For Each link In links
            If InStr(1, CStr(link), "result.xlsx", vbTextCompare) > 0 Then ThisWorkbook.BreakLink CStr(link), xlLinkTypeExcelLinks
        Next link
    End If
    With newSheet.Range("H1:M2")
        .Merge
        .WrapText = True
        .Font.Size = 10
        .Font.Color = RGB(23, 50, 77)
    End With
    If refreshMarket Then
        newSheet.Range("H1").Value = "Market data updated at " & Format(Now, "yyyy-mm-dd hh:nn")
    Else
        newSheet.Range("H1").Value = "Calculated from local data at " & Format(Now, "hh:nn:ss") & ". Click Update for new prices / FX."
    End If
    newSheet.Calculate
    resultBook.Close SaveChanges:=False
    Set resultBook = Nothing
    Application.DisplayAlerts = False
    oldSheet.Delete
    oldRenamed = False
    imported = False
    newSheet.Activate
    If Len(originalSelection) > 0 Then newSheet.Range(originalSelection).Select
    ActiveWindow.ScrollRow = savedRow
    ActiveWindow.ScrollColumn = savedColumn
    'Persist manual Update; automatic calculation keeps the usual Save behaviour.
    If refreshMarket Then ThisWorkbook.Save
    GoTo CleanUp
Failed:
    failure = Err.Description
    On Error Resume Next
    Application.DisplayAlerts = False
    If imported Then newSheet.Delete
    If oldRenamed Then oldSheet.Name = "Dashboard"
    If Not resultBook Is Nothing Then resultBook.Close SaveChanges:=False
    With ThisWorkbook.Worksheets("Dashboard").Range("H1:M2")
        .Merge
        .WrapText = True
        .Font.Size = 10
        .Font.Color = RGB(156, 50, 30)
    End With
    ThisWorkbook.Worksheets("Dashboard").Range("H1").Value = "RESULTS NOT CURRENT: " & Left$(failure, 350)
    If refreshMarket Then MsgBox failure & vbCrLf & "Your inputs remain in the workbook. See the status and local_data/last_update.log.", vbExclamation, "Update incomplete"
CleanUp:
    On Error Resume Next
    If Len(tempFolder) > 0 Then
        If Dir(inputPath) <> "" Then Kill inputPath
        If Dir(resultPath) <> "" Then Kill resultPath
        If Dir(tempFolder & separator & "result.error.txt") <> "" Then Kill tempFolder & separator & "result.error.txt"
        RmDir tempFolder
    End If
    Application.EnableEvents = oldEvents
    Application.DisplayAlerts = oldAlerts
    Application.ScreenUpdating = oldScreen
    isRunning = False
End Sub
