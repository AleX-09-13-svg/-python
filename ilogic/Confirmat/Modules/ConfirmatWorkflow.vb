' Straight VB code. Shared workflow for two and five confirmats.
Imports System
Imports Inventor
Imports System.Collections.Generic
Imports System.Diagnostics
Imports System.Globalization
Imports System.IO
Imports System.Text
Imports System.Text.RegularExpressions
Imports System.Windows.Forms

Partial Public Class ThisRule
    Private Sub RunConfirmat(count As Integer, Optional useEdgeSelection As Boolean = False)
        layoutCount = count
        edgeSelectionMode = useEdgeSelection
        app = ThisApplication
        reserved.Clear()
        referenceSides.Clear()
        referenceQueues.Clear()
        Dim logName As String = If(count = 4 AndAlso Not useEdgeSelection,
                                  "02_confirmat_4inch_fixCentr_ilogic.log",
                                  "02_confirmat_" & count.ToString() & "inch_ilogic.log")
        Dim logPath As String = System.IO.Path.Combine(ProjectRoot, logName)
        Dim transaction As Inventor.Transaction = Nothing
        Dim previousScreen As Boolean = app.ScreenUpdating
        Using writer As New StreamWriter(logPath, False, New UTF8Encoding(False))
            log = writer
            Try
                WriteLog("02 Конфирмат Native — " & count.ToString() & " шт. " & DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss"))
                If app.ActiveDocument Is Nothing OrElse app.ActiveDocument.DocumentType <> DocumentTypeEnum.kPartDocumentObject Then
                    Throw New Exception("Откройте деталь .ipt и выберите плоские грани для присадки.")
                End If
                part = DirectCast(app.ActiveDocument, PartDocument)
                comp = part.ComponentDefinition
                tg = app.TransientGeometry
                factory = app.TransientObjects
                Dim faces As List(Of Face) = SelectedFaces()
                LoadConfig()
                Dim chosen() As String = ChooseParameters()
                If chosen Is Nothing Then Return
                Dim thickness As String = chosen(0), edgeOffset As String = If(count = 1, "", chosen(1))
                ' Выбранные имена должны принадлежать пользовательской коллекции.
                Dim thicknessUser As UserParameter = comp.Parameters.UserParameters.Item(thickness)
                Dim offsetUser As UserParameter = Nothing
                If count <> 1 Then offsetUser = comp.Parameters.UserParameters.Item(edgeOffset)
                If CDbl(comp.Parameters.Item(thickness).Value) <= 0 Then Throw New Exception("Толщина должна быть положительной.")
                Dim edgeValue As Double = If(count = 1, 0.0, CDbl(comp.Parameters.Item(edgeOffset).Value))
                If count <> 1 AndAlso edgeValue < 0 Then Throw New Exception("Отступ от кромки не должен быть отрицательным.")
                ' Как в 02: глубина широкого участка равна выбранной толщине.
                For Each key As String In New String() {"outer_2pcs"}
                    Dim values As Dictionary(Of String, Object) = Block(st, key)
                    values("depth") = thickness
                    values("feature_name") = "Confirmat " & count.ToString() & "pcs counterbore"
                    st(key) = values
                Next
                Dim required As List(Of String) = RequiredParameters(thickness, edgeOffset)
                For Each name As String In required
                    Dim parameter As Inventor.Parameter = comp.Parameters.Item(name)
                Next
                Dim groups As New Dictionary(Of String, List(Of Face))
                Dim rowIndex As Integer = 0
                For Each face As Face In faces
                    rowIndex += 1
                    Dim key As String = If(layoutCount = 4 AndAlso edgeSelectionMode, "edge-row-" & rowIndex.ToString(), PlaneKey(face))
                    If Not groups.ContainsKey(key) Then groups(key) = New List(Of Face)
                    groups(key).Add(face)
                Next
                transaction = app.TransactionManager.StartTransaction(part, "02 Конфирмат " & count.ToString() & " шт. — iLogic Native")
                EnsureKeep(required)
                Dim total As Stopwatch = Stopwatch.StartNew(), phase As Stopwatch = Stopwatch.StartNew()
                app.ScreenUpdating = False
                Dim jobs As List(Of SketchJob) = BuildSketches(groups, thickness, edgeOffset, edgeValue)
                LogStage("Все эскизы", phase)
                ' Исходные грани больше не используются после начала сверления.
                BuildHoles(jobs)
                LogStage("Все отверстия", phase)
                part.Update()
                LogStage("Обновление документа", phase)
                transaction.End()
                transaction = Nothing
                app.ScreenUpdating = previousScreen
                total.Stop()
                WriteLog("Общее время построения: " & Seconds(total) & "s")
                log.Flush()
            Catch ex As Exception
                WriteLog("ОШИБКА: " & ex.ToString())
                If transaction IsNot Nothing Then
                    Try
                        transaction.Abort()
                    Catch abortError As Exception
                        WriteLog("Откат: " & abortError.Message)
                    End Try
                End If
                log.Flush()
                MessageBox.Show(ex.Message & vbCrLf & "Подробности: " & logPath, "02 — ошибка", MessageBoxButtons.OK, MessageBoxIcon.Error)
            Finally
                app.ScreenUpdating = previousScreen
            End Try
        End Using
    End Sub
End Class
