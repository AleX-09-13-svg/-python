' Straight VB code. Selection order: drilling face, mating face, orientation face.
Imports System
Imports Inventor
Imports System.Collections.Generic

Partial Public Class ThisRule
    Private Function SelectedThreeFaceJobs() As List(Of PairJob)
        Dim selected As New List(Of Face)
        For Each entity As Object In part.SelectSet
            If Not TypeOf entity Is Face Then Throw New Exception("Выберите три плоские грани в порядке: две для присадки, третья для ориентации.")
            Dim face As Face = DirectCast(entity, Face)
            If Not TypeOf face.Geometry Is Plane Then Throw New Exception("Все три выбранные грани должны быть плоскими.")
            selected.Add(face)
        Next
        If selected.Count = 0 OrElse selected.Count Mod 3 <> 0 Then
            Throw New Exception("Выберите грани тройками: узкая грань и пласть одного тела, затем грань со стороны базовой крайней стяжки.")
        End If
        Dim jobs As New List(Of PairJob)
        For i As Integer = 0 To selected.Count - 1 Step 3
            Dim first As Face = selected(i), second As Face = selected(i + 1), orientation As Face = selected(i + 2)
            Dim owner As String = first.SurfaceBody.Name
            If second.SurfaceBody.Name <> owner Then Throw New Exception("Первые две грани каждой тройки должны принадлежать одному телу.")
            If orientation Is first OrElse orientation Is second Then Throw New Exception("Третья грань должна быть отдельной гранью со стороны конца ряда стяжек.")
            If first.Evaluator.Area > second.Evaluator.Area Then
                Dim swap As Face = first : first = second : second = swap
            End If
            Dim p As Plane = DirectCast(first.Geometry, Plane), q As Plane = DirectCast(second.Geometry, Plane)
            If NormalsCrossLengthSquared(p.Normal.X, p.Normal.Y, p.Normal.Z, q.Normal.X, q.Normal.Y, q.Normal.Z) < 0.00000001 Then
                Throw New Exception("Первые две грани не должны быть параллельны.")
            End If
            bodies(owner) = first.SurfaceBody
            jobs.Add(New PairJob With {.First = first, .Second = second, .Common = SharedEdge(first, second),
                .Owner = owner, .OrientationFace = orientation})
        Next
        WriteLog("Выбрано троек граней: " & jobs.Count.ToString())
        Return jobs
    End Function

    Private Function ChooseAnchorAtStart(startDistance As Double, endDistance As Double) As Boolean
        If Double.IsNaN(startDistance) OrElse Double.IsNaN(endDistance) OrElse
            Double.IsInfinity(startDistance) OrElse Double.IsInfinity(endDistance) OrElse
            Math.Abs(startDistance - endDistance) <= Tol Then
            Throw New Exception("Третья грань не определяет сторону: выберите грань ближе к одной из крайних стяжек.")
        End If
        Return startDistance < endDistance
    End Function

    Private Function ReferenceAnchorAtStart(job As PairJob, edgeOffset As Double) As Boolean
        Dim a As Inventor.Point = job.Common.StartVertex.Point, b As Inventor.Point = job.Common.StopVertex.Point
        Dim length As Double = a.DistanceTo(b)
        Dim fraction As Double = edgeOffset / length
        Dim nearStart As Inventor.Point = tg.CreatePoint(a.X + (b.X - a.X) * fraction,
            a.Y + (b.Y - a.Y) * fraction, a.Z + (b.Z - a.Z) * fraction)
        Dim nearEnd As Inventor.Point = tg.CreatePoint(b.X + (a.X - b.X) * fraction,
            b.Y + (a.Y - b.Y) * fraction, b.Z + (a.Z - b.Z) * fraction)
        Return ChooseAnchorAtStart(job.OrientationFace.GetClosestPointTo(nearStart).DistanceTo(nearStart),
            job.OrientationFace.GetClosestPointTo(nearEnd).DistanceTo(nearEnd))
    End Function
End Class
