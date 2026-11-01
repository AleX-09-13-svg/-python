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
    Private Function BuildSide(face As Face, cups As List(Of SketchPoint), origin() As Double, direction() As Double, diameter As Double) As Job
        Dim sketch As PlanarSketch = comp.Sketches.Add(face)
        sketch.Name = AvailableName(comp.Sketches, "Petli_Side", "sketch")
        Dim job As New Job With {.Sketch = sketch}
        Dim previous As Boolean = sketch.DeferUpdates
        sketch.DeferUpdates = True
        Try
            Dim contour As List(Of Projection) = ProjectContour(sketch, face)
            Dim f As Frame = SketchFrame(sketch, contour, origin, direction)
            job.Layout = f
            Dim reference As SketchLine = contour(f.Index).Line
            Dim projections As New List(Of SketchPoint), centers As New List(Of XY)
            For Each center As SketchPoint In cups
                Dim projected As SketchPoint = DirectCast(sketch.AddByProjectingEntity(center), SketchPoint)
                projections.Add(projected) : centers.Add(Coordinates(projected.Geometry))
            Next
            Dim rows As List(Of SideRow) = SideRows(f, centers, diameter)
            Dim lines As SketchLines = sketch.SketchLines, points As SketchPoints = sketch.SketchPoints
            Dim g As GeometricConstraints = sketch.GeometricConstraints, dims As DimensionConstraints = sketch.DimensionConstraints
            For i As Integer = 0 To rows.Count - 1
                Dim r As SideRow = rows(i)
                Dim row As SketchLine = Construction(lines, projections(i), P2(r.Last))
                g.AddPerpendicular(row, reference)
                Dim front As SketchPoint = points.Add(P2(r.Front), False)
                g.AddCoincident(front, row) : g.AddCoincident(front, reference)
                Dim first As SketchPoint = points.Add(P2(r.First), True), last As SketchPoint = row.EndSketchPoint
                g.AddCoincident(first, row) : last.HoleCenter = True
                Dimension(dims, front, first, LabelPoint(r.Front, r.First, f.U), "20 mm")
                Dimension(dims, first, last, LabelPoint(r.First, r.Last, f.U), "32 mm")
                job.Points.Add(first) : job.Points.Add(last)
            Next
        Finally
            sketch.DeferUpdates = previous
        End Try
        sketch.Solve()
        Return job
    End Function
End Class
