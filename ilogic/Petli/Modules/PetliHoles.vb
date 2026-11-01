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
    Private Function DrillingDirection(sketch As PlanarSketch, face As Face) As PartFeatureExtentDirectionEnum
        ' Сохранён разворот направления, подтверждённый для Python-версии 07.
        Dim o As Inventor.Point = sketch.SketchToModelSpace(tg.CreatePoint2d(0, 0))
        Dim x As Inventor.Point = sketch.SketchToModelSpace(tg.CreatePoint2d(1, 0))
        Dim y As Inventor.Point = sketch.SketchToModelSpace(tg.CreatePoint2d(0, 1))
        Dim normal() As Double = Cross(New Double() {x.X - o.X, x.Y - o.Y, x.Z - o.Z}, New Double() {y.X - o.X, y.Y - o.Y, y.Z - o.Z})
        Dim outward As UnitVector = DirectCast(face.Geometry, Plane).Normal
        Dim sign As Double = If(face.IsParamReversed, -1.0, 1.0)
        Dim dotValue As Double = sign * Dot3(normal, New Double() {outward.X, outward.Y, outward.Z})
        Return If(dotValue > 0, PartFeatureExtentDirectionEnum.kPositiveExtentDirection, PartFeatureExtentDirectionEnum.kNegativeExtentDirection)
    End Function

    Private Function Centers(points As List(Of SketchPoint)) As ObjectCollection
        Dim result As ObjectCollection = factory.CreateObjectCollection()
        For Each point As SketchPoint In points
            result.Add(point)
        Next
        Return result
    End Function

    Private Function BodyByName(name As String) As SurfaceBody
        For Each body As SurfaceBody In comp.SurfaceBodies
            If body.Name = name Then Return body
        Next
        Throw New Exception("Целевое тело больше не найдено: " & name)
    End Function

    Private Sub AddHoles(holes As HoleFeatures, points As ObjectCollection, diameter As String, depth As String,
                         direction As PartFeatureExtentDirectionEnum, name As String, bodyName As String)
        Dim phase As Stopwatch = Stopwatch.StartNew()
        Dim placement As SketchHolePlacementDefinition = holes.CreateSketchPlacementDefinition(points)
        Dim feature As HoleFeature = holes.AddDrilledByDistanceExtent(placement, diameter, depth, direction, True)
        Try
            ' Создание отверстий перестраивает тело. Получать актуальную ссылку ПОСЛЕ Add.
            Dim bodies As ObjectCollection = factory.CreateObjectCollection()
            bodies.Add(BodyByName(bodyName))
            feature.SetAffectedBodies(bodies)
            feature.Name = AvailableName(holes, name, "feature")
        Catch ex As Exception
            ' Main отменяет всю транзакцию; повторное сверление не выполняется.
            Throw New Exception("Не удалось завершить операцию '" & name & "' для тела '" & bodyName & "'.", ex)
        End Try
        WriteLog(name & "; центров: " & points.Count.ToString() & "; тело: " & bodyName & "; " & Seconds(phase) & "s")
    End Sub
End Class
