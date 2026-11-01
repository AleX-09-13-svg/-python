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
    Private Function NewSketch(face As Face, index As Integer) As PlanarSketch
        Dim sketch As PlanarSketch = comp.Sketches.Add(face)
        sketch.Name = AvailableName(comp.Sketches, Prefix & "_" & index.ToString(), "sketch")
        OptionalDisplay("Цвет эскиза " & sketch.Name, Sub() sketch.Color = factory.CreateColor(255, 220, 0))
        Return sketch
    End Function

    Private Function ProjectFace(sketch As PlanarSketch, face As Face, common As Edge) As Projection
        Dim result As New Projection
        For Each edge As Edge In face.Edges
            Dim projected As Object = sketch.AddByProjectingEntity(edge)
            If TypeOf projected Is SketchLine Then
                Dim line As SketchLine = DirectCast(projected, SketchLine)
                result.Lines.Add(line)
                If SameEdge(edge, common) Then result.Reference = line
            End If
        Next
        If result.Reference Is Nothing Then Throw New Exception("Не удалось спроецировать общее ребро.")
        Return result
    End Function

    Private Function EndLines(reference As SketchLine, lines As List(Of SketchLine)) As List(Of SketchLine)
        Dim result As New List(Of SketchLine)
        Dim a As Point2d = reference.StartSketchPoint.Geometry, b As Point2d = reference.EndSketchPoint.Geometry
        For Each endpoint As Point2d In New Point2d() {a, b}
            Dim candidates As New List(Of SketchLine)
            For Each line As SketchLine In lines
                Dim p As Point2d = line.StartSketchPoint.Geometry, q As Point2d = line.EndSketchPoint.Geometry
                Dim cross As Double = (q.X - p.X) * (b.Y - a.Y) - (q.Y - p.Y) * (b.X - a.X)
                If Math.Abs(cross) <= Tol Then Continue For
                If p.DistanceTo(endpoint) <= Tol OrElse q.DistanceTo(endpoint) <= Tol Then candidates.Add(line)
            Next
            If candidates.Count <> 1 Then Throw New Exception("Неоднозначные боковые рёбра у конца общего ребра.")
            result.Add(candidates(0))
        Next
        Return result
    End Function

    Private Function EndReference(lines As SketchLines, g As GeometricConstraints, point As SketchPoint,
                                  reference As SketchLine, nx As Double, ny As Double) As SketchLine
        Dim p As Point2d = point.Geometry
        Dim result As SketchLine = ConstructionLine(lines, p, P2(p.X + nx, p.Y + ny))
        g.AddCoincident(result.StartSketchPoint, point)
        g.AddPerpendicular(result, reference)
        Return result
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
End Class
