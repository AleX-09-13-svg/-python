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
    Private Function P2(p As XY) As Point2d
        Return tg.CreatePoint2d(p.X, p.Y)
    End Function

    Private Function Coordinates(p As Point2d) As XY
        Return New XY(p.X, p.Y)
    End Function

    Private Function ProjectContour(sketch As PlanarSketch, face As Face) As List(Of Projection)
        If face.Edges.Count <> 4 Then Throw New Exception("Нужна прямоугольная грань без вырезов.")
        Dim result As New List(Of Projection)
        For Each edge As Edge In face.Edges
            If edge.GeometryType <> CurveTypeEnum.kLineCurve AndAlso edge.GeometryType <> CurveTypeEnum.kLineSegmentCurve Then Throw New Exception("Все рёбра должны быть прямыми.")
            Dim line As SketchLine = DirectCast(sketch.AddByProjectingEntity(edge), SketchLine)
            line.Construction = True
            Dim a As SketchPoint = line.StartSketchPoint, b As SketchPoint = line.EndSketchPoint
            result.Add(New Projection With {.Line = line, .First = a, .Last = b, .A = Coordinates(a.Geometry), .B = Coordinates(b.Geometry)})
        Next
        Return result
    End Function

    Private Function SketchFrame(sketch As PlanarSketch, contour As List(Of Projection), origin() As Double, direction() As Double) As Frame
        Dim p As Point2d = sketch.ModelToSketchSpace(tg.CreatePoint(origin(0), origin(1), origin(2)))
        Dim q As Point2d = sketch.ModelToSketchSpace(tg.CreatePoint(origin(0) + direction(0), origin(1) + direction(1), origin(2) + direction(2)))
        Dim segments As New List(Of XY())
        For Each item As Projection In contour
            segments.Add(New XY() {item.A, item.B})
        Next
        Return RectangleFrame(segments, Coordinates(p), New XY(q.X - p.X, q.Y - p.Y))
    End Function

    Private Function Construction(lines As SketchLines, first As Object, last As Object) As SketchLine
        Dim result As SketchLine = lines.AddByTwoPoints(first, last)
        result.Construction = True
        Return result
    End Function

    Private Function Dimension(dims As DimensionConstraints, first As SketchPoint, last As SketchPoint,
                               text As XY, Optional expression As String = Nothing, Optional driven As Boolean = False) As TwoPointDistanceDimConstraint
        Dim result As TwoPointDistanceDimConstraint = dims.AddTwoPointDistance(first, last, DimensionOrientationEnum.kAlignedDim, P2(text), driven)
        If expression IsNot Nothing Then result.Parameter.Expression = expression
        Return result
    End Function

    Private Function LabelPoint(a As XY, b As XY, along As XY) As XY
        Return New XY((a.X + b.X) / 2 + along.X, (a.Y + b.Y) / 2 + along.Y)
    End Function
End Class
