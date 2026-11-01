' Straight VB code. Part of the Confirmat rule; do not run separately.
Imports System
Imports Inventor
Imports System.Collections.Generic
Imports System.Diagnostics
Imports System.Globalization
Imports System.IO
Imports System.Text
Imports System.Text.RegularExpressions
Imports System.Web.Script.Serialization
Imports System.Windows.Forms

Partial Public Class ThisRule
    Private Const ProjectRoot As String = "D:\Копия Google диска\02_Скрипты\01_Скрипты для работы\For Inventor\Присадка кодом Python"
    Private Const Prefix As String = "ConfirmatSketch"
    Private Const Tol As Double = 0.00001 ' см
    Private Const StepCm As Double = 3.2
    Private app As Inventor.Application
    Private part As PartDocument
    Private comp As PartComponentDefinition
    Private tg As TransientGeometry
    Private factory As TransientObjects
    Private log As StreamWriter
    Private config As Dictionary(Of String, Object)
    Private st As Dictionary(Of String, Object)
    Private nameMap As Dictionary(Of String, String)
    Private reserved As New Dictionary(Of String, HashSet(Of String))

    Private Const Workflow As String = "confirmat"

    Private Class SketchJob
        Public Sketch As PlanarSketch
        Public Edges As New List(Of SketchPoint)
        Public Centers As New List(Of SketchPoint)
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

    Private Function Rounded(value As Double) As String
        Return Math.Round(value, 6).ToString("F6", CultureInfo.InvariantCulture)
    End Function

    Private Sub IgnoreConstraint(action As Action)
        Try
            action()
        Catch ex As Exception
            WriteLog("  Зависимость пропущена: " & ex.Message)
        End Try
    End Sub

    Private Sub OptionalDisplay(label As String, action As Action)
        ' Как в Python: отказ оформления записать, но не отменять присадку.
        ' Этот обработчик не применяется к геометрии, размерам и отверстиям.
        Try
            action()
        Catch ex As Exception
            WriteLog("  Оформление пропущено (" & label & "): " & ex.Message)
        End Try
    End Sub

    Private Function Seconds(watch As Stopwatch) As String
        Return watch.Elapsed.TotalSeconds.ToString("F3", CultureInfo.InvariantCulture)
    End Function

    Private Sub LogStage(label As String, watch As Stopwatch)
        WriteLog(label & ": " & Seconds(watch) & "s")
        watch.Restart()
    End Sub

    Private Sub WriteLog(message As String)
        log.WriteLine(message)
        log.Flush()
    End Sub
End Class
