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
    Private Function BuildFacade(face As Face, side As Face, origin() As Double, direction() As Double,
                                 diameter As Double, pilotDiameter As Double) As Job
        Dim sketch As PlanarSketch = comp.Sketches.Add(face)
        sketch.Name = AvailableName(comp.Sketches, "Petli", "sketch")
        Dim job As New Job With {.Sketch = sketch}
        Dim previous As Boolean = sketch.DeferUpdates
        sketch.DeferUpdates = True
        Try
            Dim contour As List(Of Projection) = ProjectContour(sketch, face)
            Dim f As Frame = SketchFrame(sketch, contour, origin, direction)
            job.Layout = f
            Dim positions() As Double = FacadePositions(f, diameter, pilotDiameter)
            Dim projected As Integer = 0
            For Each edge As Edge In side.Edges
                Try
                    sketch.AddByProjectingEntity(edge) : projected += 1
                Catch
                    ' Перпендикулярные эскизу рёбра могут вырождаться в точки.
                End Try
            Next
            If projected = 0 Then Throw New Exception("Не удалось спроецировать боковину на фасад.")
            Dim reference As Projection = contour(f.Index)
            Dim lines As SketchLines = sketch.SketchLines, points As SketchPoints = sketch.SketchPoints
            Dim g As GeometricConstraints = sketch.GeometricConstraints, dims As DimensionConstraints = sketch.DimensionConstraints
            Dim control As TwoPointDistanceDimConstraint = Dimension(dims, reference.First, reference.Last, f.At(f.Length / 2, -3), Nothing, True)
            Dim lengthName As String = AvailableName(comp.Parameters, "Petli_Length", "parameter")
            control.Parameter.Name = lengthName
            Dim offset As SketchLine = Construction(lines, reference.First, P2(f.At(0, 2.2)))
            Dim offsetStart As SketchPoint = offset.StartSketchPoint, offsetEnd As SketchPoint = offset.EndSketchPoint
            g.AddPerpendicular(offset, reference.Line)
            Dimension(dims, offsetStart, offsetEnd, f.At(-2, 1.1), "22 mm")
            Dim axis As SketchLine = Construction(lines, offsetEnd, P2(f.At(f.Length, 2.2)))
            Dim axisStart As SketchPoint = axis.StartSketchPoint, axisEnd As SketchPoint = axis.EndSketchPoint
            g.AddParallel(axis, reference.Line)
            Dimension(dims, axisStart, axisEnd, f.At(f.Length / 2, 4), lengthName)
            For i As Integer = 0 To positions.Length - 1
                Dim t As Double = positions(i)
                Dim center As SketchPoint = points.Add(P2(f.At(t, 2.2)), True)
                g.AddCoincident(center, axis)
                Dim expression As String = "100 mm + (" & lengthName & " - 200 mm) * " & i.ToString(CultureInfo.InvariantCulture) & " / " & (positions.Length - 1).ToString(CultureInfo.InvariantCulture)
                Dimension(dims, axisStart, center, f.At(t / 2, 5 + i), expression)
                job.Points.Add(center)
                Dim anchor As SketchLine = Construction(lines, center, P2(f.At(t, 3.15)))
                Dim a As SketchPoint = anchor.StartSketchPoint, b As SketchPoint = anchor.EndSketchPoint
                g.AddPerpendicular(anchor, axis)
                Dimension(dims, a, b, f.At(t + 1, 2.675), "9.5 mm")
                Dim row As SketchLine = Construction(lines, P2(f.At(t - 2.25, 3.15)), P2(f.At(t + 2.25, 3.15)))
                Dim rowStart As SketchPoint = row.StartSketchPoint, rowEnd As SketchPoint = row.EndSketchPoint
                g.AddParallel(row, axis) : g.AddMidpoint(b, row)
                Dimension(dims, rowStart, rowEnd, f.At(t, 4.15), "45 mm")
                rowStart.HoleCenter = True : rowEnd.HoleCenter = True
                job.Pilots.Add(rowStart) : job.Pilots.Add(rowEnd)
            Next
        Finally
            sketch.DeferUpdates = previous
        End Try
        sketch.Solve()
        Return job
    End Function
End Class
