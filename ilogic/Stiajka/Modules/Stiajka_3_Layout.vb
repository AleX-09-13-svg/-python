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
        Dim symmetry As SketchLine = ConstructionLine(lines, P2(cx, cy), P2(cx + nx, cy + ny))
        IgnoreConstraint(Sub() g.AddPerpendicular(axis, symmetry))
        IgnoreConstraint(Sub() g.AddMidpoint(symmetry.StartSketchPoint, axis))
        Dim referenceLength As Double = LineLength(reference)
        Dim anchorAtStart As Boolean = StartsAtCommonBeginning(sk, a, b, job)
        Dim positions() As Double = TiePositions(referenceLength, edgeValue, anchorAtStart)
        Dim dowels() As Double = DowelPositions(positions)
        For Each position As Double In positions
            Dim tie As SketchPoint = points.Add(P2(cx + ux * position, cy + uy * position), False)
            job.Outer.Add(tie)
            g.AddCoincident(tie, axis)
        Next
        For Each position As Double In dowels
            Dim dowel As SketchPoint = points.Add(P2(cx + ux * position, cy + uy * position), False)
            job.Inner.Add(dowel)
            g.AddCoincident(dowel, axis)
        Next
        g.AddSymmetry(job.Outer(0), job.Outer(2), symmetry)
        g.AddSymmetry(job.Inner(0), job.Inner(1), symmetry)
        Dim t As Double = (positions(0) + dowels(0)) / 2
        Dim inset As Object = dims.AddTwoPointDistance(job.Outer(0), job.Inner(0), DimensionOrientationEnum.kAlignedDim,
            P2(cx + ux * t + nx * 3, cy + uy * t + ny * 3), False)
        inset.Parameter.Expression = "32 mm"
        For i As Integer = 2 To 3
            Dim textPosition As Double = (positions(1) + dowels(i)) / 2
            Dim centralInset As Object = dims.AddTwoPointDistance(job.Outer(1), job.Inner(i),
                DimensionOrientationEnum.kAlignedDim, P2(cx + ux * textPosition + nx * (4 + i),
                    cy + uy * textPosition + ny * (4 + i)), False)
            centralInset.Parameter.Expression = "32 mm"
        Next
        ControlDimensions(dims, reference, job.Outer, P2(cx + nx * 4, cy + ny * 4),
                          P2(cx + nx * 2, cy + ny * 2), P2(cx + nx * 6, cy + ny * 6), edgeParam, index, anchorAtStart)
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
            Dim anchorAtStart As Boolean = StartsAtCommonBeginning(sk, a, b, job)
            Dim positions() As Double = TiePositions(length, edgeValue, anchorAtStart)
            For i As Integer = 0 To TieCount - 1
                Dim tie As SketchPoint = points.Add(P2(cx + ux * positions(i), cy + uy * positions(i)), False)
                job.Cups.Add(tie)
                g.AddCoincident(tie, axis)
            Next
            g.AddSymmetry(job.Cups(0), job.Cups(2), anchor)
            ControlDimensions(dims, reference, job.Cups, P2(cx + nx * 4, cy + ny * 4),
                              P2(cx + nx * 2, cy + ny * 2), P2(cx + nx * 6, cy + ny * 6), edgeParam, index, anchorAtStart)
            Dim offsetDim As Object = dims.AddTwoPointDistance(anchor.StartSketchPoint, anchor.EndSketchPoint,
                DimensionOrientationEnum.kAlignedDim, P2(cx - nx * offsetValue / 2 + ux * 2, cy - ny * offsetValue / 2 + uy * 2), False)
            offsetDim.Parameter.Expression = offsetParam
        Finally
            sk.DeferUpdates = False
        End Try
        OptionalDisplay("Скрытие размеров " & sk.Name, Sub() sk.DimensionsVisible = False)
    End Sub

    Private Sub ControlDimensions(dims As DimensionConstraints, reference As SketchLine, ties As List(Of SketchPoint),
                                  controlText As Point2d, spanText As Point2d, pitchText As Point2d,
                                  edgeParam As String, index As Integer, anchorAtStart As Boolean)
        Dim control As Object = dims.AddTwoPointDistance(reference.StartSketchPoint, reference.EndSketchPoint,
                                                         DimensionOrientationEnum.kAlignedDim, controlText, True)
        Dim name As String = AvailableName(comp.Parameters, "Long_edge_" & index.ToString(), "parameter")
        control.Parameter.Name = name
        Dim span As Object = dims.AddTwoPointDistance(ties(2), ties(0), DimensionOrientationEnum.kAlignedDim, spanText, False)
        span.Parameter.Name = AvailableName(comp.Parameters, "Расстояние_между_точками", "parameter")
        span.Parameter.Expression = name & " - " & edgeParam & " * 2"
        Dim pitch As Object = dims.AddTwoPointDistance(ties(If(anchorAtStart, 0, 2)), ties(1),
            DimensionOrientationEnum.kAlignedDim, pitchText, False)
        pitch.Parameter.Name = AvailableName(comp.Parameters, "Шаг_средней_стяжки_3", "parameter")
        pitch.Parameter.Expression = "floor((" & span.Parameter.Name & " / 2) / 32 mm) * 32 mm"
    End Sub

    Private Function StartsAtCommonBeginning(sk As PlanarSketch, a As Point2d, b As Point2d, job As PairJob) As Boolean
        ' Направления осей могут отличаться; физическая база выбрана по третьей грани.
        Dim axisDirection As Inventor.Vector = sk.SketchToModelSpace(a).VectorTo(sk.SketchToModelSpace(b))
        Dim commonDirection As Inventor.Vector = job.Common.StartVertex.Point.VectorTo(job.Common.StopVertex.Point)
        Return AnchorForAxis(job.AnchorAtCommonStart, axisDirection.DotProduct(commonDirection))
    End Function

    Private Function AnchorForAxis(anchorAtCommonStart As Boolean, directionDot As Double) As Boolean
        Return (directionDot >= 0) = anchorAtCommonStart
    End Function

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
        Dim span As Double = length - 2 * offset
        If Double.IsNaN(span) OrElse Double.IsInfinity(span) OrElse offset < 0 OrElse span <= 2 * StepCm + 0.000001 Then
            Throw New Exception("Недостаточно места для трёх стяжек со шкантами: расстояние крайних стяжек должно быть больше 64 мм.")
        End If
        Return span
    End Function

    Private Function MiddlePitch(span As Double) As Double
        Dim steps As Double = span / 2 / StepCm
        If Math.Abs(steps - Math.Round(steps)) <= 0.000000000001 Then steps = Math.Round(steps)
        Return Math.Floor(steps) * StepCm
    End Function

    Private Function TiePositions(length As Double, offset As Double, Optional anchorAtStart As Boolean = True) As Double()
        Dim span As Double = PointSpan(length, offset)
        Dim pitch As Double = MiddlePitch(span)
        Dim middle As Double = If(anchorAtStart, -span / 2 + pitch, span / 2 - pitch)
        Return New Double() {-span / 2, middle, span / 2}
    End Function

    Private Function DowelPositions(ties As Double()) As Double()
        ' Сначала два крайних шканта внутрь ряда, затем два шканта по обе стороны средней стяжки.
        Return New Double() {ties(0) + StepCm, ties(2) - StepCm,
            ties(1) - StepCm, ties(1) + StepCm}
    End Function

    Private Function DiameterValue(expression As String) As Double
        Try
            Return CDbl(comp.Parameters.Item(expression).Value)
        Catch
            ' Числовое выражение, например 8 mm, вместо имени параметра.
        End Try
        Return CDbl(part.UnitsOfMeasure.GetValueFromExpression(expression, UnitsTypeEnum.kCentimeterLengthUnits))
    End Function

    Private Sub ValidateLayout(length As Double, offset As Double)
        Dim tieD As Double = Math.Max(DiameterValue(ResolveExpression(Text(Block(st, "Otv_stijki_v_torec"), "diameter", "8 mm"))),
                                      DiameterValue(ResolveExpression(Text(Block(st, "Otv_stijki_v_bokoviny"), "diameter", "5 mm"))))
        Dim dowelD As Double = Math.Max(DiameterValue(ResolveExpression(Text(Block(st, "shkant_v_plast"), "diameter", "8 mm"))),
                                        DiameterValue(ResolveExpression(Text(Block(st, "shkant_v_torets"), "diameter", "8 mm"))))
        Dim ties() As Double = TiePositions(length, offset)
        Dim dowels() As Double = DowelPositions(ties)
        ValidateClearance(ties, dowels, tieD, dowelD, DiameterValue(SettingParameter("diameter", "Стяжка_D")))
    End Sub

    Private Sub ValidateClearance(ties As Double(), dowels As Double(), tieD As Double, dowelD As Double, cupD As Double)
        Dim centers As New List(Of Double)(ties)
        centers.AddRange(dowels)
        For i As Integer = 0 To centers.Count - 1
            For j As Integer = i + 1 To centers.Count - 1
                Dim di As Double = If(i < TieCount, tieD, dowelD)
                Dim dj As Double = If(j < TieCount, tieD, dowelD)
                If Math.Abs(centers(i) - centers(j)) <= (di + dj) / 2 + Tol Then
                    Throw New Exception("Отверстия стяжек или шкантов пересекаются. Уменьшите отступ или выберите более длинное ребро.")
                End If
            Next
        Next
        If Math.Min(ties(1) - ties(0), ties(2) - ties(1)) <= cupD + Tol Then Throw New Exception("Чашки стяжек пересекаются: недостаточный шаг.")
    End Sub

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
