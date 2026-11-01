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
    Private Function Positive(value As Double) As Boolean
        Return Not Double.IsNaN(value) AndAlso Not Double.IsInfinity(value) AndAlso value > 0
    End Function

    Private Function Distance(a As XY, b As XY) As Double
        Return Math.Sqrt((a.X - b.X) ^ 2 + (a.Y - b.Y) ^ 2)
    End Function

    Private Function Dot(a As XY, b As XY) As Double
        Return a.X * b.X + a.Y * b.Y
    End Function

    Private Function RectangleFrame(segments As List(Of XY()), origin As XY, direction As XY) As Frame
        If segments.Count <> 4 Then Throw New Exception("Нужна прямоугольная грань без вырезов.")
        Dim norm As Double = Math.Sqrt(Dot(direction, direction))
        If norm < Tol Then Throw New Exception("Не удалось определить направление ребра.")
        Dim u As New XY(direction.X / norm, direction.Y / norm), n As New XY(-u.Y, u.X)
        Dim corners As New List(Of XY)
        For Each segment As XY() In segments
            If Distance(segment(0), segment(1)) < Tol Then Throw New Exception("Нулевое ребро.")
            For Each p As XY In segment
                Dim found As Boolean = False
                For Each q As XY In corners
                    If Distance(p, q) < Tol Then found = True
                Next
                If Not found Then corners.Add(p)
            Next
        Next
        If corners.Count <> 4 Then Throw New Exception("Контур должен иметь четыре угла.")
        Dim lo As Double = Double.PositiveInfinity, hi As Double = Double.NegativeInfinity
        Dim left As Double = Double.PositiveInfinity, right As Double = Double.NegativeInfinity
        Dim center As New XY(0, 0)
        For Each p As XY In corners
            lo = Math.Min(lo, Dot(p, u)) : hi = Math.Max(hi, Dot(p, u))
            left = Math.Min(left, Dot(p, n)) : right = Math.Max(right, Dot(p, n))
            center.X += p.X / 4 : center.Y += p.Y / 4
        Next
        If hi - lo < Tol OrElse right - left < Tol Then Throw New Exception("Вырожденный контур.")
        For Each p As XY In corners
            If Math.Min(Math.Abs(Dot(p, u) - lo), Math.Abs(Dot(p, u) - hi)) > Tol OrElse
               Math.Min(Math.Abs(Dot(p, n) - left), Math.Abs(Dot(p, n) - right)) > Tol Then
                Throw New Exception("Кромки должны быть параллельны и перпендикулярны второй плоскости.")
            End If
        Next
        Dim candidates As New List(Of KeyValuePair(Of Double, Integer))
        For i As Integer = 0 To segments.Count - 1
            Dim a As XY = segments(i)(0), b As XY = segments(i)(1)
            Dim da As Double = Dot(a, u) - Dot(b, u), db As Double = Dot(a, n) - Dot(b, n)
            If Math.Abs(da) > Tol AndAlso Math.Abs(db) > Tol Then Throw New Exception("Грань должна быть прямоугольной.")
            If Math.Abs(db) < Tol Then candidates.Add(New KeyValuePair(Of Double, Integer)(Math.Abs(Dot(a, n) - Dot(origin, n)), i))
        Next
        candidates.Sort(Function(a, b) a.Key.CompareTo(b.Key))
        If candidates.Count <> 2 OrElse Math.Abs(candidates(0).Key - candidates(1).Key) < Tol Then Throw New Exception("Неоднозначная сторона размещения петель.")
        Dim index As Integer = candidates(0).Value
        Dim start As XY = segments(index)(0), finish As XY = segments(index)(1)
        Dim length As Double = Distance(start, finish)
        Dim along As New XY((finish.X - start.X) / length, (finish.Y - start.Y) / length)
        Dim inward As New XY(-along.Y, along.X)
        If Dot(New XY(center.X - start.X, center.Y - start.Y), inward) < 0 Then inward = New XY(-inward.X, -inward.Y)
        Return New Frame With {.Index = index, .A = start, .U = along, .N = inward, .Length = length, .Width = right - left}
    End Function

    Private Function Cross(a() As Double, b() As Double) As Double()
        Return New Double() {a(1) * b(2) - a(2) * b(1), a(2) * b(0) - a(0) * b(2), a(0) * b(1) - a(1) * b(0)}
    End Function

    Private Function Dot3(a() As Double, b() As Double) As Double
        Return a(0) * b(0) + a(1) * b(1) + a(2) * b(2)
    End Function

    Private Sub Intersection(first As Plane, second As Plane, ByRef origin() As Double, ByRef direction() As Double)
        Dim n1 As UnitVector = first.Normal, n2 As UnitVector = second.Normal
        Dim a() As Double = {n1.X, n1.Y, n1.Z}, b() As Double = {n2.X, n2.Y, n2.Z}
        If Math.Abs(Dot3(a, b)) > Tol Then Throw New Exception("Фасад и боковина должны быть перпендикулярны.")
        direction = Cross(a, b)
        Dim norm As Double = Dot3(direction, direction)
        If norm < 0.00000001 Then Throw New Exception("Плоскости параллельны.")
        Dim p1 As Inventor.Point = first.RootPoint, p2 As Inventor.Point = second.RootPoint
        Dim c1 As Double = Dot3(a, New Double() {p1.X, p1.Y, p1.Z}), c2 As Double = Dot3(b, New Double() {p2.X, p2.Y, p2.Z})
        Dim bd() As Double = Cross(b, direction), da() As Double = Cross(direction, a)
        origin = New Double(2) {}
        For i As Integer = 0 To 2
            origin(i) = (c1 * bd(i) + c2 * da(i)) / norm
        Next
    End Sub
End Class
