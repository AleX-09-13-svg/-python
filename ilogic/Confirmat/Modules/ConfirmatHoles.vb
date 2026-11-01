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
    Private Function Placement(points As List(Of SketchPoint)) As SketchHolePlacementDefinition
        Dim collection As ObjectCollection = factory.CreateObjectCollection()
        Dim seen As New HashSet(Of String)
        For Each point As SketchPoint In points
            Dim p As Point2d = point.Geometry
            If seen.Add(Rounded(p.X) & ":" & Rounded(p.Y)) Then
                point.HoleCenter = True
                collection.Add(point)
            End If
        Next
        Return comp.Features.HoleFeatures.CreateSketchPlacementDefinition(collection)
    End Function

    Private Function AddCounterbore(points As List(Of SketchPoint), outerKey As String, innerKey As String, defaultName As String) As List(Of HoleFeature)
        Dim outer As Dictionary(Of String, Object) = Block(st, outerKey), inner As Dictionary(Of String, Object) = Block(st, innerKey)
        Dim diameter As String = ResolveExpression(Text(inner, "diameter", "")), depth As String = ResolveExpression(Text(inner, "depth", ""))
        Dim cbDiameter As String = ResolveExpression(Text(outer, "diameter", "")), cbDepth As String = ResolveExpression(Text(outer, "depth", ""))
        Dim name As String = Text(outer, "feature_name", defaultName)
        Dim holes As HoleFeatures = comp.Features.HoleFeatures
        Dim result As New List(Of HoleFeature)
        Dim position As SketchHolePlacementDefinition = Placement(points)
        Dim feature As HoleFeature = Nothing
        Try
            feature = holes.AddCBoreByDistanceExtent(position, diameter, depth, PartFeatureExtentDirectionEnum.kPositiveExtentDirection, cbDiameter, cbDepth, True)
        Catch ex As Exception
            WriteLog("Counterbore API: " & ex.Message & "; создаются два соосных сверления.")
        End Try
        If feature IsNot Nothing Then
            result.Add(feature)
        Else
            ' Как в Python: резерв из двух операций с теми же центрами.
            result.Add(holes.AddDrilledByDistanceExtent(Placement(points), diameter, depth, PartFeatureExtentDirectionEnum.kPositiveExtentDirection, True))
            result.Add(holes.AddDrilledByDistanceExtent(Placement(points), cbDiameter, cbDepth, PartFeatureExtentDirectionEnum.kPositiveExtentDirection, True))
        End If
        For i As Integer = 0 To result.Count - 1
            ' Ошибки после создания не запускают повторное сверление: Main откатит транзакцию.
            result(i).Name = AvailableName(holes, name & If(i = 0, "", " outer"), "feature")
            Dim affected As ObjectCollection = factory.CreateObjectCollection()
            For Each body As SurfaceBody In comp.SurfaceBodies
                If body.IsSolid Then affected.Add(body)
            Next
            If affected.Count > 1 Then result(i).SetAffectedBodies(affected)
        Next
        WriteLog(name & "; центров: " & points.Count.ToString() & "; операций: " & result.Count.ToString())
        Return result
    End Function

    Private Function Direction(settings As Dictionary(Of String, Object)) As PartFeatureExtentDirectionEnum
        Dim value As String = Text(settings, "direction", "positive").ToLowerInvariant()
        If value = "negative" Then Return PartFeatureExtentDirectionEnum.kNegativeExtentDirection
        If value = "positive" Then Return PartFeatureExtentDirectionEnum.kPositiveExtentDirection
        Throw New Exception("Неизвестное направление отверстия: " & value)
    End Function

    Private Sub BuildHoles(jobs As List(Of SketchJob), countParameter As Inventor.Parameter)
        For Each job As SketchJob In jobs
            Dim shareableSketch As Object = job.Sketch
            Try
                shareableSketch.Shared = True
            Catch
            End Try
            Dim edgeFeatures As List(Of HoleFeature) = AddCounterbore(job.Edges, "outer_2pcs", "inner_2pcs", "Confirmat edges")
            Dim centerFeatures As List(Of HoleFeature) = AddCounterbore(job.Centers, "outer_3pcs", "inner_3pcs", "Confirmat center")
            For Each feature As HoleFeature In centerFeatures
                ' Условие сохраняется в модели и реагирует на изменение количества.
                feature.SetSuppressionCondition(countParameter, 60417, 2)
            Next
            OptionalDisplay("Скрытие эскиза", Sub() job.Sketch.Visible = False)
        Next
    End Sub
End Class
