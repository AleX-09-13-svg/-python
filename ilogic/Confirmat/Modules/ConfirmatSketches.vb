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
    Private Function SelectedFaces() As List(Of Face)
        Dim result As New List(Of Face), seen As New HashSet(Of String)
        For Each entity As Object In part.SelectSet
            If Not TypeOf entity Is Face Then Throw New Exception("Выберите только плоские грани детали.")
            Dim face As Face = DirectCast(entity, Face)
            If Not TypeOf face.Geometry Is Plane Then Throw New Exception("Для присадки требуются плоские грани.")
            Dim key As String = face.SurfaceBody.Name & ":" & face.TransientKey.ToString()
            If seen.Add(key) Then result.Add(face)
        Next
        If result.Count = 0 Then Throw New Exception("Выберите грани для присадки перед запуском правила.")
        Return result
    End Function

    Private Sub BuildFace(job As SketchJob, face As Face, edgeOffset As String, edgeValue As Double, index As Integer)
        Dim sketch As PlanarSketch = job.Sketch
        Dim projected As New List(Of SketchLine)
        For Each edge As Edge In face.Edges
            Dim entity As Object = sketch.AddByProjectingEntity(edge)
            If TypeOf entity Is SketchLine Then projected.Add(DirectCast(entity, SketchLine))
        Next
        If projected.Count < 2 Then Throw New Exception("Недостаточно прямых рёбер для построения оси присадки.")
        ' Как в 02: ось между серединами двух самых коротких проекций.
        Dim lengths As New Dictionary(Of SketchLine, Double)
        For Each line As SketchLine In projected
            lengths(line) = LineLength(line)
        Next
        projected.Sort(Function(first As SketchLine, second As SketchLine) lengths(first).CompareTo(lengths(second)))
        Dim short1 As SketchLine = projected(0), short2 As SketchLine = projected(1)
        Dim a As Point2d = Midpoint(short1), b As Point2d = Midpoint(short2)
        Dim dx As Double = b.X - a.X, dy As Double = b.Y - a.Y
        Dim length As Double = Math.Sqrt(dx * dx + dy * dy)
        Dim span As Double = PointSpan(length, edgeValue)
        Dim ux As Double = dx / length, uy As Double = dy / length, nx As Double = -uy, ny As Double = ux
        Dim cx As Double = (a.X + b.X) / 2, cy As Double = (a.Y + b.Y) / 2
        Dim lines As SketchLines = sketch.SketchLines, points As SketchPoints = sketch.SketchPoints
        Dim g As GeometricConstraints = sketch.GeometricConstraints, dims As DimensionConstraints = sketch.DimensionConstraints
        Dim axis As SketchLine = ConstructionLine(lines, a, b)
        g.AddMidpoint(axis.StartSketchPoint, short1)
        g.AddMidpoint(axis.EndSketchPoint, short2)
        Dim symmetry As SketchLine = ConstructionLine(lines, P2(cx, cy), P2(cx + nx, cy + ny))
        g.AddMidpoint(symmetry.StartSketchPoint, axis)
        g.AddPerpendicular(symmetry, axis)
        Dim left As SketchPoint = points.Add(P2(cx - ux * span / 2, cy - uy * span / 2), False)
        Dim right As SketchPoint = points.Add(P2(cx + ux * span / 2, cy + uy * span / 2), False)
        Dim center As SketchPoint = points.Add(P2(cx, cy), False)
        g.AddCoincident(left, axis)
        g.AddCoincident(right, axis)
        g.AddSymmetry(left, right, symmetry)
        g.AddMidpoint(center, axis)
        Dim control As Object = dims.AddTwoPointDistance(axis.StartSketchPoint, axis.EndSketchPoint,
            DimensionOrientationEnum.kAlignedDim, P2(cx + nx * 4, cy + ny * 4), True)
        Dim name As String = AvailableName(comp.Parameters, "Long_edge_" & index.ToString(), "parameter")
        control.Parameter.Name = name
        Dim distance As Object = dims.AddTwoPointDistance(right, left, DimensionOrientationEnum.kAlignedDim,
                                                          P2(cx + nx * 2, cy + ny * 2), False)
        distance.Parameter.Name = AvailableName(comp.Parameters, "Расстояние_между_точками", "parameter")
        distance.Parameter.Expression = "floor((" & name & " - " & edgeOffset & " * 2) / 32 mm) * 32 mm"
        job.Edges.Add(left) : job.Edges.Add(right) : job.Centers.Add(center)
    End Sub

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

    Private Function PointSpan(length As Double, offset As Double) As Double
        Dim span As Double = Math.Floor((length - 2 * offset) / StepCm) * StepCm
        If offset < 0 OrElse span < 2 * StepCm Then Throw New Exception("Недостаточно места: расстояние крайних точек должно быть не меньше 64 мм.")
        Return span
    End Function

    Private Function ConstructionLine(lines As SketchLines, a As Point2d, b As Point2d) As SketchLine
        Dim result As SketchLine = lines.AddByTwoPoints(a, b)
        result.Construction = True
        Return result
    End Function

    Private Function LineLength(line As SketchLine) As Double
        Return line.StartSketchPoint.Geometry.DistanceTo(line.EndSketchPoint.Geometry)
    End Function

    Private Function Midpoint(line As SketchLine) As Point2d
        Dim a As Point2d = line.StartSketchPoint.Geometry, b As Point2d = line.EndSketchPoint.Geometry
        Return P2((a.X + b.X) / 2, (a.Y + b.Y) / 2)
    End Function

    Private Function P2(x As Double, y As Double) As Point2d
        Return tg.CreatePoint2d(x, y)
    End Function

    Private Function BuildSketches(groups As Dictionary(Of String, List(Of Face)), thickness As String,
                                   edgeOffset As String, edgeValue As Double) As List(Of SketchJob)
        Dim jobs As New List(Of SketchJob)
        Dim faceIndex As Integer = 0, planeIndex As Integer = 0
        For Each group As List(Of Face) In groups.Values
            planeIndex += 1
            Dim plane As WorkPlane = comp.WorkPlanes.AddByPlaneAndOffset(group(0), thickness)
            plane.Name = AvailableName(comp.WorkPlanes, Prefix & "_OffsetPlane_" & planeIndex.ToString(), "plane")
            OptionalDisplay("Скрытие рабочей плоскости", Sub() plane.Visible = False)
            Dim sketch As PlanarSketch = comp.Sketches.Add(plane)
            sketch.Name = AvailableName(comp.Sketches, Prefix & "_" & planeIndex.ToString(), "sketch")
            OptionalDisplay("Цвет эскиза", Sub() sketch.Color = factory.CreateColor(255, 220, 0))
            Dim job As New SketchJob With {.Sketch = sketch}
            sketch.DeferUpdates = True
            Try
                For Each face As Face In group
                    faceIndex += 1
                    BuildFace(job, face, edgeOffset, edgeValue, faceIndex)
                Next
            Finally
                sketch.DeferUpdates = False
            End Try
            OptionalDisplay("Скрытие размеров", Sub() sketch.DimensionsVisible = False)
            jobs.Add(job)
        Next
        Return jobs
    End Function
End Class
