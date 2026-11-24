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

    Private Function OuterContourFrame(segments As List(Of XY()), referencePoint As XY) As Frame
        If segments Is Nothing OrElse segments.Count = 0 Then Throw New Exception("У внешнего контура нет рёбер.")
        ' Ось раскладки определяем по наружной границе, а не по пересечению
        ' плоскостей фасада и боковины. Это допускает небольшой/любой поворот
        ' внешнего контура относительно второй плоскости.
        Dim axisLength As Double = 0, axis As XY = Nothing
        For Each segment As XY() In segments
            Dim dx As Double = segment(1).X - segment(0).X, dy As Double = segment(1).Y - segment(0).Y
            Dim segmentMagnitude As Double = Math.Sqrt(dx * dx + dy * dy)
            If segmentMagnitude < Tol Then Throw New Exception("Нулевое ребро во внешнем контуре.")
            If segmentMagnitude > axisLength Then
                axisLength = segmentMagnitude
                axis = New XY(dx / segmentMagnitude, dy / segmentMagnitude)
            End If
        Next
        If axisLength < Tol OrElse axis Is Nothing Then Throw New Exception("Не удалось определить направление внешнего контура.")
        Dim u As XY = axis
        Dim n As New XY(-u.Y, u.X)
        Dim lo As Double = Double.PositiveInfinity
        Dim hi As Double = Double.NegativeInfinity
        Dim left As Double = Double.PositiveInfinity
        Dim right As Double = Double.NegativeInfinity
        For Each segment As XY() In segments
            For Each p As XY In segment
                Dim alongCoordinate As Double = Dot(p, u)
                Dim acrossCoordinate As Double = Dot(p, n)
                lo = Math.Min(lo, alongCoordinate) : hi = Math.Max(hi, alongCoordinate)
                left = Math.Min(left, acrossCoordinate) : right = Math.Max(right, acrossCoordinate)
            Next
        Next
        If hi - lo < Tol OrElse right - left < Tol Then Throw New Exception("Вырожденный контур.")
        Dim center As New XY(u.X * ((lo + hi) / 2) + n.X * ((left + right) / 2),
                             u.Y * ((lo + hi) / 2) + n.Y * ((left + right) / 2))
        Dim candidates As New List(Of KeyValuePair(Of Double, Integer))
        For i As Integer = 0 To segments.Count - 1
            Dim a As XY = segments(i)(0), b As XY = segments(i)(1)
            Dim db As Double = Dot(a, n) - Dot(b, n)
            If Math.Abs(db) < Tol Then
                Dim level As Double = Dot(a, n)
                candidates.Add(New KeyValuePair(Of Double, Integer)(Math.Abs(level - Dot(referencePoint, n)), i))
            End If
        Next
        candidates.Sort(Function(a, b) a.Key.CompareTo(b.Key))
        If candidates.Count = 0 Then Throw New Exception("Не удалось найти наружную сторону для размещения петель.")
        Dim index As Integer = candidates(0).Value
        Dim start As XY = segments(index)(0), finish As XY = segments(index)(1)
        Dim forward As Boolean = Dot(New XY(finish.X - start.X, finish.Y - start.Y), u) > 0
        Dim frameLength As Double = hi - lo
        Dim frameDirection As XY = If(forward, u, New XY(-u.X, -u.Y))
        start = If(forward, New XY(u.X * lo + n.X * Dot(start, n), u.Y * lo + n.Y * Dot(start, n)),
                            New XY(u.X * hi + n.X * Dot(start, n), u.Y * hi + n.Y * Dot(start, n)))
        Dim inward As New XY(-frameDirection.Y, frameDirection.X)
        If Dot(New XY(center.X - start.X, center.Y - start.Y), inward) < 0 Then inward = New XY(-inward.X, -inward.Y)
        Return New Frame With {.Index = index, .A = start, .U = frameDirection, .N = inward, .Length = frameLength, .Width = right - left}
    End Function

    Private Function Cross(a() As Double, b() As Double) As Double()
        Return New Double() {a(1) * b(2) - a(2) * b(1), a(2) * b(0) - a(0) * b(2), a(0) * b(1) - a(1) * b(0)}
    End Function

    Private Function Dot3(a() As Double, b() As Double) As Double
        Return a(0) * b(0) + a(1) * b(1) + a(2) * b(2)
    End Function

    Private Sub Intersection(first As Plane, second As Plane, ByRef origin() As Double)
        Dim n1 As UnitVector = first.Normal, n2 As UnitVector = second.Normal
        Dim a() As Double = {n1.X, n1.Y, n1.Z}, b() As Double = {n2.X, n2.Y, n2.Z}
        If Math.Abs(Dot3(a, b)) > Tol Then Throw New Exception("Фасад и боковина должны быть перпендикулярны.")
        Dim direction() As Double = Cross(a, b)
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
