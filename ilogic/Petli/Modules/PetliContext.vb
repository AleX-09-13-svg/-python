' Straight VB code. Partial ThisRule; do not run separately.
Imports System
Imports Inventor
Imports System.Collections.Generic
Imports System.Diagnostics
Imports System.Globalization
Imports System.IO
Imports System.Text
Imports System.Windows.Forms

Partial Public Class ThisRule
    Private Const Workflow As String = "petli"
    Private Const ProjectRoot As String = "D:\Копия Google диска\02_Скрипты\01_Скрипты для работы\For Inventor\Присадка кодом Python"
    Private Const CupD As String = "Петля_D_присадки"
    Private Const CupH As String = "Стяжкаh_резьбаШтока_Петля"
    Private Const PilotD As String = "Наколка_D"
    Private Const PilotH As String = "Наколка_Глубина"
    Private Const Tol As Double = 0.00001 ' Внутренние единицы — сантиметры.
    Private app As Inventor.Application
    Private part As PartDocument
    Private comp As PartComponentDefinition
    Private tg As TransientGeometry
    Private factory As TransientObjects
    Private log As StreamWriter
    Private reserved As New Dictionary(Of String, HashSet(Of String))

    Private Class XY
        Public X As Double, Y As Double
        Public Sub New(xValue As Double, yValue As Double)
            X = xValue : Y = yValue
        End Sub
    End Class

    Private Class Frame
        Public Index As Integer
        Public A As XY, U As XY, N As XY
        Public Length As Double, Width As Double
        Public Function At(t As Double, offset As Double) As XY
            Return New XY(A.X + U.X * t + N.X * offset, A.Y + U.Y * t + N.Y * offset)
        End Function
    End Class

    Private Class Projection
        Public Line As SketchLine
        Public First As SketchPoint, Last As SketchPoint
        Public A As XY, B As XY
    End Class

    Private Class Job
        Public Sketch As PlanarSketch
        Public Points As New List(Of SketchPoint)
        Public Pilots As New List(Of SketchPoint)
        Public Layout As Frame
    End Class

    Private Class SideRow
        Public Front As XY, First As XY, Last As XY
    End Class

    Private Function AvailableName(collection As Object, basis As String, category As String) As String
        If Not reserved.ContainsKey(category) Then reserved(category) = New HashSet(Of String)
        Dim index As Integer = 0
        Do
            Dim candidate As String = basis & If(index = 0, "", "_" & index.ToString())
            index += 1
            If reserved(category).Contains(candidate) Then Continue Do
            Try
                Dim existing As Object = collection.Item(candidate)
            Catch
                reserved(category).Add(candidate)
                Return candidate
            End Try
        Loop
    End Function

    Private Function Seconds(watch As Stopwatch) As String
        Return watch.Elapsed.TotalSeconds.ToString("F3", CultureInfo.InvariantCulture)
    End Function

    Private Sub WriteLog(message As String)
        log.WriteLine(message) : log.Flush()
    End Sub

    Private Sub LogStage(label As String, watch As Stopwatch)
        WriteLog(label & ": " & Seconds(watch) & "s") : watch.Restart()
    End Sub
End Class
