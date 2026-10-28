Attribute VB_Name = "ThisWorkbook"
Attribute VB_Base = "0{00020819-0000-0000-C000-000000000046}"
Attribute VB_GlobalNameSpace = False
Attribute VB_Creatable = False
Attribute VB_PredeclaredId = True
Attribute VB_Exposed = True
Attribute VB_TemplateDerived = False
Attribute VB_Customizable = True
Option Explicit

Private Sub Workbook_SheetChange(ByVal Sh As Object, ByVal Target As Range)
    If Sh.Name <> "Dashboard" Then Exit Sub
    If Application.Intersect(Target, Sh.Range("B4:B8,E3:E4,A27:F226")) Is Nothing Then Exit Sub
    Module1.QueueCalculation
End Sub

Private Sub Workbook_BeforeClose(Cancel As Boolean)
    Module1.CancelPendingCalculation
End Sub

Private Sub Workbook_Activate()
    Module1.ResumePendingCalculation
End Sub
