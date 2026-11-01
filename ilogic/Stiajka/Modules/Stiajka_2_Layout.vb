' Straight VB code. Shared part of ThisRule; do not run separately.
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
    Private Sub BuildFirst(job As PairJob, edgeParam As String, edgeValue As Double, index As Integer)
        Dim sk As PlanarSketch = job.Sketch1
        Dim projection As Projection = ProjectFace(sk, job.First, job.Common)
        Dim reference As SketchLine = projection.Reference
        Dim ends As List(Of SketchLine) = EndLines(reference, projection.Lines)
        Dim a As Point2d = Midpoint(ends(0)), b As Point2d = Midpoint(ends(1))
        Dim dx As Double = b.X - a.X, dy As Double = b.Y - a.Y
        Dim length As Double = Math.Sqrt(dx * dx + dy * dy)
        If length <= Tol Then Throw New Exception("Совпадают середины боковых рёбер.")
        Dim ux As Double = dx / length, uy As Double = dy / length
        Dim nx As Double = -uy, ny As Double = ux
        Dim cx As Double = (a.X + b.X) / 2, cy As Double = (a.Y + b.Y) / 2
        Dim lines As SketchLines = sk.SketchLines
        Dim g As GeometricConstraints = sk.GeometricConstraints
        Dim points As SketchPoints = sk.SketchPoints
        Dim dims As DimensionConstraints = sk.DimensionConstraints
        Dim axis As SketchLine = ConstructionLine(lines, a, b)
        IgnoreConstraint(Sub() g.AddMidpoint(axis.StartSketchPoint, ends(0)))
        IgnoreConstraint(Sub() g.AddMidpoint(axis.EndSketchPoint, ends(1)))
        Dim symmetry As SketchLine = ConstructionLine(lines, P2(cx - nx, cy - ny), P2(cx + nx, cy + ny))
        IgnoreConstraint(Sub() g.AddPerpendicular(axis, symmetry))
        IgnoreConstraint(Sub() g.AddMidpoint(symmetry.StartSketchPoint, axis))
        Dim referenceLength As Double = LineLength(reference)
        Dim span As Double = PointSpan(referenceLength, edgeValue), outer As Double = span / 2
        Dim left As SketchPoint = points.Add(P2(cx - ux * outer, cy - uy * outer), False)
        Dim right As SketchPoint = points.Add(P2(cx + ux * outer, cy + uy * outer), False)
        Dim center As SketchPoint = points.Add(P2(cx, cy), False)
        job.Outer.Add(left) : job.Outer.Add(right)
        IgnoreConstraint(Sub() g.AddCoincident(left, axis))
        IgnoreConstraint(Sub() g.AddCoincident(right, axis))
        IgnoreConstraint(Sub() g.AddCoincident(center, axis))
        IgnoreConstraint(Sub() g.AddCoincident(center, symmetry))
        IgnoreConstraint(Sub() g.AddSymmetry(left, right, symmetry))
        If span < StepCm * 3 Then
            job.Inner.Add(center)
        Else
            Dim inner As Double = outer - StepCm
            Dim li As SketchPoint = points.Add(P2(cx - ux * inner, cy - uy * inner), False)
            Dim ri As SketchPoint = points.Add(P2(cx + ux * inner, cy + uy * inner), False)
            job.Inner.Add(li) : job.Inner.Add(ri)
            IgnoreConstraint(Sub() g.AddCoincident(li, axis))
            IgnoreConstraint(Sub() g.AddCoincident(ri, axis))
            IgnoreConstraint(Sub() g.AddSymmetry(li, ri, symmetry))
            Dim inset As Object = dims.AddTwoPointDistance(left, li, DimensionOrientationEnum.kAlignedDim,
                                                          P2(cx - ux * (outer - 1.6) + nx * 2, cy - uy * (outer - 1.6) + ny * 2), False)
            inset.Parameter.Expression = "32 mm"
        End If
        ControlDimensions(dims, reference, left, right, P2(cx + nx * 4, cy + ny * 4),
                          P2(cx + nx * 2, cy + ny * 2), edgeParam, index)
    End Sub

    Private Sub BuildSecond(job As PairJob, edgeParam As String, edgeValue As Double,
                            offsetParam As String, offsetValue As Double, index As Integer)
        Dim sk As PlanarSketch = NewSketch(job.Second, index)
        job.Sketch2 = sk
        sk.DeferUpdates = True
        Try
            Dim projected As Projection = ProjectFace(sk, job.Second, job.Common)
            Dim reference As SketchLine = projected.Reference
            Dim a As Point2d = reference.StartSketchPoint.Geometry, b As Point2d = reference.EndSketchPoint.Geometry
            Dim length As Double = LineLength(reference)
            Dim ux As Double = (b.X - a.X) / length, uy As Double = (b.Y - a.Y) / length
            Dim nx As Double = -uy, ny As Double = ux
            Dim inside As Point2d = sk.ModelToSketchSpace(job.Second.PointOnFace)
            If (inside.X - a.X) * nx + (inside.Y - a.Y) * ny < 0 Then nx = -nx : ny = -ny
            Dim lines As SketchLines = sk.SketchLines
            Dim g As GeometricConstraints = sk.GeometricConstraints
            Dim points As SketchPoints = sk.SketchPoints
            Dim dims As DimensionConstraints = sk.DimensionConstraints
            Dim leftSide As SketchLine = Nothing, rightSide As SketchLine = Nothing
            For Each candidate As SketchLine In projected.Lines
                Dim p As Point2d = candidate.StartSketchPoint.Geometry, q As Point2d = candidate.EndSketchPoint.Geometry
                Dim t1 As Double = (p.X - a.X) * ux + (p.Y - a.Y) * uy
                Dim t2 As Double = (q.X - a.X) * ux + (q.Y - a.Y) * uy
                If Math.Abs(t1) < 0.0001 AndAlso Math.Abs(t2) < 0.0001 Then leftSide = candidate
                If Math.Abs(t1 - length) < 0.0001 AndAlso Math.Abs(t2 - length) < 0.0001 Then rightSide = candidate
            Next
            If leftSide Is Nothing Then leftSide = EndReference(lines, g, reference.StartSketchPoint, reference, nx, ny)
            If rightSide Is Nothing Then rightSide = EndReference(lines, g, reference.EndSketchPoint, reference, nx, ny)
            Dim cx As Double = (a.X + b.X) / 2 + nx * offsetValue
            Dim cy As Double = (a.Y + b.Y) / 2 + ny * offsetValue
            Dim axis As SketchLine = ConstructionLine(lines, P2(a.X + nx * offsetValue, a.Y + ny * offsetValue),
                                                      P2(b.X + nx * offsetValue, b.Y + ny * offsetValue))
            g.AddParallel(axis, reference)
            g.AddCoincident(axis.StartSketchPoint, leftSide)
            g.AddCoincident(axis.EndSketchPoint, rightSide)
            Dim anchor As SketchLine = ConstructionLine(lines, P2(cx - nx * offsetValue, cy - ny * offsetValue), P2(cx, cy))
            g.AddCoincident(anchor.StartSketchPoint, reference)
            g.AddMidpoint(anchor.EndSketchPoint, axis)
            g.AddPerpendicular(anchor, axis)
            Dim outer As Double = PointSpan(length, edgeValue) / 2
            Dim left As SketchPoint = points.Add(P2(cx - ux * outer, cy - uy * outer), False)
            Dim right As SketchPoint = points.Add(P2(cx + ux * outer, cy + uy * outer), False)
            job.Cups.Add(left) : job.Cups.Add(right)
            IgnoreConstraint(Sub() g.AddCoincident(left, axis))
            IgnoreConstraint(Sub() g.AddCoincident(right, axis))
            IgnoreConstraint(Sub() g.AddSymmetry(left, right, anchor))
            ControlDimensions(dims, reference, left, right, P2(cx + nx * 4, cy + ny * 4),
                              P2(cx + nx * 2, cy + ny * 2), edgeParam, index)
            Dim offsetDim As Object = dims.AddTwoPointDistance(anchor.StartSketchPoint, anchor.EndSketchPoint,
                DimensionOrientationEnum.kAlignedDim, P2(cx - nx * offsetValue / 2 + ux * 2, cy - ny * offsetValue / 2 + uy * 2), False)
            offsetDim.Parameter.Expression = offsetParam
        Finally
            sk.DeferUpdates = False
        End Try
        OptionalDisplay("Скрытие размеров " & sk.Name, Sub() sk.DimensionsVisible = False)
    End Sub

    Private Sub ControlDimensions(dims As DimensionConstraints, reference As SketchLine, left As SketchPoint,
                                  right As SketchPoint, controlText As Point2d, spanText As Point2d,
                                  edgeParam As String, index As Integer)
        Dim control As Object = dims.AddTwoPointDistance(reference.StartSketchPoint, reference.EndSketchPoint,
                                                         DimensionOrientationEnum.kAlignedDim, controlText, True)
        Dim name As String = AvailableName(comp.Parameters, "Long_edge_" & index.ToString(), "parameter")
        control.Parameter.Name = name
        Dim span As Object = dims.AddTwoPointDistance(right, left, DimensionOrientationEnum.kAlignedDim, spanText, False)
        span.Parameter.Name = AvailableName(comp.Parameters, "Расстояние_между_точками", "parameter")
        span.Parameter.Expression = "floor((" & name & " - " & edgeParam & " * 2) / 32 mm) * 32 mm"
    End Sub

    Private Function RequiredParameters(edgeParam As String) As List(Of String)
        Dim result As New List(Of String)
        result.Add(edgeParam)
        result.Add(SettingParameter("offset", "Стяжка_отступ"))
        result.Add(SettingParameter("diameter", "Стяжка_D"))
        result.Add(SettingParameter("depth", "Стяжка_h"))
        For Each key As String In New String() {"Otv_stijki_v_torec", "Otv_stijki_v_bokoviny", "shkant_v_plast", "shkant_v_torets"}
            Dim settings As Dictionary(Of String, Object) = Block(st, key)
            For Each field As String In New String() {"diameter", "depth"}
                Dim name As String = ResolveName(Text(settings, field, ""))
                If Regex.IsMatch(name, "^[^\W\d]\w*$") AndAlso Not result.Contains(name) Then result.Add(name)
            Next
        Next
        Dim cup As Dictionary(Of String, Object) = Block(st, "Chashka stiajki")
        For Each field As String In New String() {"diameter_parameter", "depth_parameter"}
            Dim name As String = ResolveName(Text(cup, field, ""))
            If name <> "" AndAlso Not result.Contains(name) Then result.Add(name)
        Next
        Dim unique As New List(Of String)
        For Each name As String In result
            If Not unique.Contains(name) Then unique.Add(name)
        Next
        Return unique
    End Function

    Private Function PointSpan(length As Double, offset As Double) As Double
        Dim span As Double = Math.Floor((length - 2 * offset) / StepCm) * StepCm
        If offset < 0 OrElse span < 2 * StepCm Then Throw New Exception("Недостаточно места: расстояние крайних точек должно быть не меньше 64 мм.")
        Return span
    End Function

    Private Sub BuildSketches(jobs As List(Of PairJob), edgeParam As String, edgeValue As Double,
                              offsetParam As String, offsetValue As Double, phase As Stopwatch)
        Dim groups As New Dictionary(Of String, List(Of PairJob))
        For Each job As PairJob In jobs
            Dim key As String = PlaneKey(job.First)
            If Not groups.ContainsKey(key) Then groups(key) = New List(Of PairJob)
            groups(key).Add(job)
        Next
        Dim index As Integer = 0
        Dim faceIndex As Integer = 0
        For Each group As List(Of PairJob) In groups.Values
            index += 1
            Dim sketch As PlanarSketch = NewSketch(group(0).First, index)
            sketch.DeferUpdates = True
            Try
                For Each job As PairJob In group
                    faceIndex += 1
                    job.Sketch1 = sketch
                    BuildFirst(job, edgeParam, edgeValue, faceIndex)
                Next
            Finally
                sketch.DeferUpdates = False
            End Try
            OptionalDisplay("Скрытие размеров " & sketch.Name, Sub() sketch.DimensionsVisible = False)
        Next
        LogStage("Первые эскизы", phase)
        For i As Integer = 0 To jobs.Count - 1
            BuildSecond(jobs(i), edgeParam, edgeValue, offsetParam, offsetValue, i + 2)
        Next
        LogStage("Вторые эскизы", phase)
    End Sub
End Class
