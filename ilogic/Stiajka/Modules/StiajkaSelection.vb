' Straight VB code. Shared part of ThisRule; do not run separately.
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
    Private Function SelectedPairs() As List(Of PairJob)
        Dim groups As New Dictionary(Of String, List(Of Face))
        Dim seen As New HashSet(Of String)
        For Each entity As Object In part.SelectSet
            If Not TypeOf entity Is Face Then Continue For
            Dim face As Face = DirectCast(entity, Face)
            If Not TypeOf face.Geometry Is Plane Then Throw New Exception("Выбирайте только плоские грани.")
            Dim owner As String = face.SurfaceBody.Name
            Dim key As String = owner & ":" & face.TransientKey.ToString()
            If Not seen.Add(key) Then Continue For
            If Not groups.ContainsKey(owner) Then groups(owner) = New List(Of Face)
            groups(owner).Add(face)
            bodies(owner) = face.SurfaceBody
        Next
        If groups.Count = 0 Then Throw New Exception("Выберите узкую грань и пласть на каждом теле.")
        Dim result As New List(Of PairJob)
        For Each entry As KeyValuePair(Of String, List(Of Face)) In groups
            If entry.Value.Count <> 2 Then Throw New Exception("Тело '" & entry.Key & "': требуется ровно две выбранные грани.")
            Dim a As Face = entry.Value(0), b As Face = entry.Value(1)
            If a.Evaluator.Area > b.Evaluator.Area Then
                Dim swap As Face = a : a = b : b = swap
            End If
            Dim p As Plane = DirectCast(a.Geometry, Plane), q As Plane = DirectCast(b.Geometry, Plane)
            Dim n1 As UnitVector = p.Normal, n2 As UnitVector = q.Normal
            If NormalsCrossLengthSquared(n1.X, n1.Y, n1.Z, n2.X, n2.Y, n2.Z) < 0.00000001 Then
                Throw New Exception("Выбранные грани параллельны.")
            End If
            result.Add(New PairJob With {.First = a, .Second = b, .Common = SharedEdge(a, b), .Owner = entry.Key})
        Next
        WriteLog("Выбрано пар граней: " & result.Count.ToString())
        Return result
    End Function

    Private Function SharedEdge(first As Face, second As Face) As Edge
        Dim matches As New List(Of Edge)
        For Each a As Edge In first.Edges
            If CInt(a.GeometryType) <> 5122 AndAlso CInt(a.GeometryType) <> 5123 Then Continue For
            For Each b As Edge In second.Edges
                If SameEdge(a, b) Then
                    matches.Add(a)
                    Exit For
                End If
            Next
        Next
        If matches.Count <> 1 Then Throw New Exception("Требуется одно общее прямое ребро выбранных граней. Найдено: " & matches.Count.ToString())
        Return matches(0)
    End Function

    Private Function SameEdge(a As Edge, b As Edge) As Boolean
        If CInt(b.GeometryType) <> 5122 AndAlso CInt(b.GeometryType) <> 5123 Then Return False
        Dim a1 As Inventor.Point = a.StartVertex.Point, a2 As Inventor.Point = a.StopVertex.Point
        Dim b1 As Inventor.Point = b.StartVertex.Point, b2 As Inventor.Point = b.StopVertex.Point
        Return (a1.DistanceTo(b1) <= Tol AndAlso a2.DistanceTo(b2) <= Tol) OrElse
               (a1.DistanceTo(b2) <= Tol AndAlso a2.DistanceTo(b1) <= Tol)
    End Function

    Private Function FindNeighbor(job As PairJob) As String
        Dim samples As New List(Of Inventor.Point)
        For Each p As SketchPoint In job.Outer
            samples.Add(job.Sketch1.SketchToModelSpace(p.Geometry))
        Next
        For Each p As SketchPoint In job.Inner
            samples.Add(job.Sketch1.SketchToModelSpace(p.Geometry))
        Next
        WriteLog("Поиск соседа для '" & job.Owner & "'; центров: " & samples.Count.ToString() &
                 "; допуск проверки грани: 0.01 мм; скрытые тела включены.")
        Dim sourcePlane As Plane = DirectCast(job.First.Geometry, Plane)
        WriteLog("  Плоскость торца: точка " & PointForLog(sourcePlane.RootPoint) &
                 "; нормаль: " & Rounded(sourcePlane.Normal.X) & "; " &
                 Rounded(sourcePlane.Normal.Y) & "; " & Rounded(sourcePlane.Normal.Z))
        Dim found As New HashSet(Of String)
        Dim neighborTolerance As Double = 0.001 ' см = 0.01 мм
        For Each body As SurfaceBody In comp.SurfaceBodies
            Dim name As String = body.Name
            If name = job.Owner OrElse found.Contains(name) Then Continue For
            If Not body.IsSolid Then
                WriteLog("  Отклонено '" & name & "': тело не твердотельное.")
                Continue For
            End If
            Dim faceIndex As Integer = 0
            For Each face As Face In body.Faces
                faceIndex += 1
                If Not TypeOf face.Geometry Is Plane Then Continue For
                If Not SamePlaneWithin(job.First, face, neighborTolerance) Then Continue For
                Dim contains As Boolean = True
                Dim sampleIndex As Integer = 0
                For Each p As Inventor.Point In samples
                    sampleIndex += 1
                    Dim distance As Double
                    Try
                        distance = face.GetClosestPointTo(p).DistanceTo(p)
                    Catch ex As System.Runtime.InteropServices.COMException
                        WriteLog("  Проверка грани " & faceIndex.ToString() & " тела '" & name &
                                 "' не выполнена: " & ex.Message)
                        contains = False
                        Exit For
                    End Try
                    If distance > neighborTolerance Then
                        WriteLog("  Грань " & faceIndex.ToString() & " тела '" & name &
                                 "' не покрывает центр " & sampleIndex.ToString() &
                                 "; расстояние: " & Rounded(distance * 10) & " мм.")
                        contains = False
                        Exit For
                    End If
                Next
                If contains Then
                    found.Add(name)
                    bodies(name) = body
                    WriteLog("  Найдена совпадающая грань тела '" & name & "'.")
                    Exit For
                End If
            Next
        Next
        If found.Count <> 1 Then Throw New Exception("Тело '" & job.Owner & "': требуется один сосед с совпадающей гранью. Найдено: " & found.Count.ToString())
        Dim result As String = Nothing
        For Each name As String In found
            result = name
        Next
        WriteLog("Тело выбранной грани: " & job.Owner & "; соседнее тело: " & result)
        Return result
    End Function

    Private Function PointForLog(point As Inventor.Point) As String
        Return "(" & Rounded(point.X * 10) & "; " & Rounded(point.Y * 10) & "; " &
               Rounded(point.Z * 10) & ") мм"
    End Function

    Private Function CurrentBody(name As String) As SurfaceBody
        If bodies.ContainsKey(name) Then
            Try
                If bodies(name).Name = name Then Return bodies(name)
            Catch
            End Try
        End If
        For Each body As SurfaceBody In comp.SurfaceBodies
            If body.Name = name Then bodies(name) = body : Return body
        Next
        Throw New Exception("Целевое тело не найдено: " & name)
    End Function

    Private Function PlaneKey(face As Face) As String
        Dim plane As Plane = DirectCast(face.Geometry, Plane)
        Dim n As UnitVector = plane.Normal, p As Inventor.Point = plane.RootPoint
        Dim sign As Double = 1
        For Each value As Double In New Double() {n.X, n.Y, n.Z}
            If Math.Abs(value) > 0.001 Then
                sign = If(value < 0, -1.0, 1.0)
                Exit For
            End If
        Next
        Dim distance As Double = (n.X * p.X + n.Y * p.Y + n.Z * p.Z) * sign
        Return Math.Round(n.X * sign, 3).ToString("F3", CultureInfo.InvariantCulture) & ":" &
               Math.Round(n.Y * sign, 3).ToString("F3", CultureInfo.InvariantCulture) & ":" &
               Math.Round(n.Z * sign, 3).ToString("F3", CultureInfo.InvariantCulture) & ":" &
               Math.Round(distance, 3).ToString("F3", CultureInfo.InvariantCulture)
    End Function

    Private Function SamePlaneWithin(a As Face, b As Face, tolerance As Double) As Boolean
        Dim p As Plane = TryCast(a.Geometry, Plane), q As Plane = TryCast(b.Geometry, Plane)
        If p Is Nothing OrElse q Is Nothing Then Return False
        Dim n As UnitVector = p.Normal, m As UnitVector = q.Normal
        Dim dot As Double = n.X * m.X + n.Y * m.Y + n.Z * m.Z
        Dim x As Inventor.Point = p.RootPoint, y As Inventor.Point = q.RootPoint
        Return Math.Abs(Math.Abs(dot) - 1) <= Tol AndAlso
               Math.Abs((y.X - x.X) * n.X + (y.Y - x.Y) * n.Y + (y.Z - x.Z) * n.Z) <= tolerance
    End Function

    Private Function NormalsCrossLengthSquared(ax As Double, ay As Double, az As Double,
                                               bx As Double, by As Double, bz As Double) As Double
        ' Числовой расчёт не требует приведения результата UnitVector.CrossProduct
        ' к несовместимому COM-интерфейсу Inventor.Vector.
        Dim x As Double = ay * bz - az * by
        Dim y As Double = az * bx - ax * bz
        Dim z As Double = ax * by - ay * bx
        Return x * x + y * y + z * z
    End Function
End Class
