' Straight VB code. Reference side for the middle confirmat.
Imports System
Imports Inventor
Imports System.Collections.Generic

Partial Public Class ThisRule
    Private Function FiveConfirmatFaces() As List(Of Face)
        Dim selected As New List(Of Object)
        For Each entity As Object In part.SelectSet
            selected.Add(entity)
        Next
        If selected.Count = 0 OrElse selected.Count Mod 2 <> 0 Then
            Throw New Exception("Выберите грани и ориентиры парами: грань присадки, затем торцевая кромка или грань со стороны отсчёта.")
        End If
        Dim faces As New List(Of Face), seen As New HashSet(Of String)
        For i As Integer = 0 To selected.Count - 1 Step 2
            Dim face As Face = TryCast(selected(i), Face)
            If face Is Nothing OrElse Not TypeOf face.Geometry Is Plane Then Throw New Exception("Первой в каждой паре выберите плоскую грань для присадки.")
            Dim reference As Object = selected(i + 1)
            If TypeOf reference Is Face Then
                Dim side As Face = DirectCast(reference, Face)
                If Not TypeOf side.Geometry Is Plane Then Throw New Exception("Ориентирующая грань должна быть плоской.")
                If side.SurfaceBody.Name = face.SurfaceBody.Name AndAlso side.TransientKey = face.TransientKey Then
                    Throw New Exception("Для ориентира выберите отдельную торцевую грань или кромку.")
                End If
            ElseIf TypeOf reference Is Edge Then
                Dim edge As Edge = DirectCast(reference, Edge)
                If CInt(edge.GeometryType) <> 5122 AndAlso CInt(edge.GeometryType) <> 5123 Then Throw New Exception("Для отсчёта выберите прямую кромку у одного конца ряда.")
            Else
                Throw New Exception("После грани присадки выберите торцевую кромку или грань со стороны базового конфирмата.")
            End If
            Dim key As String = face.SurfaceBody.Name & ":" & face.TransientKey.ToString()
            If Not seen.Add(key) Then Throw New Exception("Каждую грань присадки выбирайте один раз.")
            faces.Add(face)
            referenceSides.Add(face, reference)
        Next
        Return faces
    End Function

    Private Function SegmentDistance(px As Double, py As Double, pz As Double,
        ax As Double, ay As Double, az As Double, bx As Double, by As Double, bz As Double) As Double
        Dim dx As Double = bx - ax, dy As Double = by - ay, dz As Double = bz - az
        Dim length2 As Double = dx * dx + dy * dy + dz * dz
        If length2 <= Tol * Tol Then Throw New Exception("Выбрана кромка нулевой длины.")
        Dim t As Double = Math.Max(0, Math.Min(1, ((px - ax) * dx + (py - ay) * dy + (pz - az) * dz) / length2))
        Return Math.Sqrt((px - ax - t * dx) ^ 2 + (py - ay - t * dy) ^ 2 + (pz - az - t * dz) ^ 2)
    End Function

    Private Function ReferenceDistance(reference As Object, point As Inventor.Point) As Double
        If TypeOf reference Is Face Then Return DirectCast(reference, Face).GetClosestPointTo(point).DistanceTo(point)
        Dim edge As Edge = DirectCast(reference, Edge)
        Dim a As Inventor.Point = edge.StartVertex.Point, b As Inventor.Point = edge.StopVertex.Point
        Return SegmentDistance(point.X, point.Y, point.Z, a.X, a.Y, a.Z, b.X, b.Y, b.Z)
    End Function

    Private Function AnchorByDistances(leftDistance As Double, rightDistance As Double) As Boolean
        If Math.Abs(leftDistance - rightDistance) <= Tol Then
            Throw New Exception("Кромка или грань не определяет сторону отсчёта: выберите ориентир ближе к одному из крайних конфирматов.")
        End If
        Return leftDistance < rightDistance
    End Function

    Private Function MiddleConfirmatPitch(span As Double) As Double
        Dim steps As Double = span / 2 / StepCm
        If Math.Abs(steps - Math.Round(steps)) <= 0.000000000001 Then steps = Math.Round(steps)
        Return Math.Floor(steps) * StepCm
    End Function
End Class
