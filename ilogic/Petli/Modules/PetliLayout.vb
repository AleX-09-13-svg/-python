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
    Private Function HingeCount(heightMm As Double) As Integer
        If Not Positive(heightMm) Then Throw New Exception("Размер фасада должен быть положительным.")
        If heightMm < 1000 Then Return 2
        If heightMm < 1600 Then Return 3
        If heightMm < 2000 Then Return 4
        Return 5
    End Function

    Private Function FacadePositions(frame As Frame, diameter As Double, pilotDiameter As Double) As Double()
        Dim count As Integer = HingeCount(frame.Length * 10)
        If Not Positive(diameter) OrElse Not Positive(pilotDiameter) Then Throw New Exception("Диаметры должны быть положительными.")
        Dim stepValue As Double = (frame.Length - 20) / (count - 1)
        If frame.Length <= 20 OrElse stepValue <= diameter OrElse diameter / 2 > Math.Min(2.2, Math.Min(frame.Width - 2.2, 10)) Then
            Throw New Exception("Недостаточно места для чашек с отступами 100 и 22 мм.")
        End If
        Dim result(count - 1) As Double
        Dim pilots As New List(Of XY)
        For i As Integer = 0 To count - 1
            result(i) = 10 + i * stepValue
            pilots.Add(New XY(result(i) - 2.25, 3.15))
            pilots.Add(New XY(result(i) + 2.25, 3.15))
        Next
        Dim radius As Double = pilotDiameter / 2
        For i As Integer = 0 To pilots.Count - 1
            Dim p As XY = pilots(i)
            If radius > Math.Min(Math.Min(p.X, frame.Length - p.X), Math.Min(p.Y, frame.Width - p.Y)) Then Throw New Exception("Наколки выходят за границы фасада.")
            For Each t As Double In result
                If Distance(p, New XY(t, 2.2)) <= radius + diameter / 2 Then Throw New Exception("Наколки пересекаются с чашками.")
            Next
            For j As Integer = 0 To i - 1
                If Distance(p, pilots(j)) <= pilotDiameter Then Throw New Exception("Наколки пересекаются между собой.")
            Next
        Next
        Return result
    End Function

    Private Function SideRows(frame As Frame, centers As List(Of XY), diameter As Double) As List(Of SideRow)
        If Not Positive(diameter) Then Throw New Exception("Диаметр наколки должен быть положительным.")
        Dim result As New List(Of SideRow), checked As New List(Of XY)
        For Each p As XY In centers
            Dim t As Double = Dot(New XY(p.X - frame.A.X, p.Y - frame.A.Y), frame.U)
            If diameter / 2 > Math.Min(Math.Min(t, frame.Length - t), Math.Min(2, frame.Width - 5.2)) Then
                Throw New Exception("Недостаточно места на боковине для отступов 20 и 52 мм.")
            End If
            Dim row As New SideRow With {.Front = frame.At(t, 0), .First = frame.At(t, 2), .Last = frame.At(t, 5.2)}
            For Each point As XY In New XY() {row.First, row.Last}
                For Each other As XY In checked
                    If Distance(point, other) <= diameter Then Throw New Exception("Отверстия на боковине пересекаются.")
                Next
                checked.Add(point)
            Next
            result.Add(row)
        Next
        Return result
    End Function
End Class
