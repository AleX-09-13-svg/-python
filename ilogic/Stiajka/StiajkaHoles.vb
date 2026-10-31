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
    Private Sub CreateBatches(jobs As List(Of PairJob), key As String, inner As Boolean, neighbor As Boolean,
                             defaultD As String, defaultH As String, defaultName As String)
        Dim sets As New Dictionary(Of String, List(Of SketchPoint))
        Dim owners As New Dictionary(Of String, String)
        Dim groupedJobs As New Dictionary(Of String, List(Of PairJob))
        For Each job As PairJob In jobs
            Dim bodyName As String = If(neighbor, job.Neighbor, job.Owner)
            Dim groupKey As String = bodyName & vbTab & job.Sketch1.Name
            If Not sets.ContainsKey(groupKey) Then
                sets(groupKey) = New List(Of SketchPoint)
                groupedJobs(groupKey) = New List(Of PairJob)
            End If
            sets(groupKey).AddRange(If(inner, job.Inner, job.Outer))
            groupedJobs(groupKey).Add(job)
            owners(groupKey) = bodyName
        Next
        Dim settings As Dictionary(Of String, Object) = Block(st, key)
        For Each entry As KeyValuePair(Of String, List(Of SketchPoint)) In sets
            Try
                AddHoles(entry.Value, ResolveExpression(Text(settings, "diameter", defaultD)),
                         ResolveExpression(Text(settings, "depth", defaultH)), Direction(settings),
                         Text(settings, "feature_name", defaultName), owners(entry.Key))
            Catch ex As PostCreationException
                Throw
            Catch ex As Exception
                If groupedJobs(entry.Key).Count = 1 Then Throw
                WriteLog("Пакет " & key & " отклонён, обработка по парам: " & ex.Message)
                For Each job As PairJob In groupedJobs(entry.Key)
                    AddHoles(If(inner, job.Inner, job.Outer), ResolveExpression(Text(settings, "diameter", defaultD)),
                             ResolveExpression(Text(settings, "depth", defaultH)), Direction(settings),
                             Text(settings, "feature_name", defaultName), owners(entry.Key))
                Next
            End Try
        Next
    End Sub

    Private Sub AddHoles(points As List(Of SketchPoint), diameter As String, depth As String,
                         direction As PartFeatureExtentDirectionEnum, name As String, bodyName As String)
        Dim watch As Stopwatch = Stopwatch.StartNew()
        Dim centers As ObjectCollection = factory.CreateObjectCollection()
        Dim seen As New HashSet(Of String)
        For Each p As SketchPoint In points
            Dim key As String = Rounded(p.Geometry.X) & ":" & Rounded(p.Geometry.Y)
            If seen.Add(key) Then
                p.HoleCenter = True
                centers.Add(p)
            End If
        Next
        Dim holes As HoleFeatures = comp.Features.HoleFeatures
        Dim placement As SketchHolePlacementDefinition = holes.CreateSketchPlacementDefinition(centers)
        Dim feature As HoleFeature = holes.AddDrilledByDistanceExtent(placement, diameter, depth, direction, True)
        Try
            feature.Name = AvailableName(holes, name, "feature")
            Dim affected As ObjectCollection = factory.CreateObjectCollection()
            affected.Add(CurrentBody(bodyName))
            feature.SetAffectedBodies(affected)
        Catch ex As Exception
            ' Не повторять сверление, если сама операция уже создана.
            ' Main отменит всю транзакцию вместе с этой операцией.
            Throw New PostCreationException("Не удалось завершить операцию '" & name & "' для тела '" & bodyName & "'.", ex)
        End Try
        WriteLog("  " & name & "; тело: " & bodyName & "; центров: " & centers.Count.ToString() & "; " & Seconds(watch) & "s")
    End Sub

    Private Function Direction(settings As Dictionary(Of String, Object)) As PartFeatureExtentDirectionEnum
        Dim value As String = Text(settings, "direction", "positive").ToLowerInvariant()
        If value = "negative" Then Return PartFeatureExtentDirectionEnum.kNegativeExtentDirection
        If value = "positive" Then Return PartFeatureExtentDirectionEnum.kPositiveExtentDirection
        Throw New Exception("Неизвестное направление отверстия: " & value)
    End Function

    Private Sub BuildHoles(jobs As List(Of PairJob))
        For Each job As PairJob In jobs
            Dim shareableSketch As Object = job.Sketch1
            Try
                shareableSketch.Shared = True
            Catch
            End Try
            OptionalDisplay("Видимость первого эскиза", Sub() job.Sketch1.Visible = True)
        Next
        CreateBatches(jobs, "Otv_stijki_v_torec", False, False, "8 mm", "34 mm", "Stiajka outer 8x34")
        CreateBatches(jobs, "Otv_stijki_v_bokoviny", False, True, "5 mm", "13 mm", "Stiajka outer 5x13")
        CreateBatches(jobs, "shkant_v_plast", True, True, "8 mm", "10 mm", "Shkant 8x10")
        CreateBatches(jobs, "shkant_v_torets", True, False, "8 mm", "20 mm", "Shkant 8x20")
        Dim cup As Dictionary(Of String, Object) = Block(st, "Chashka stiajki")
        For Each job As PairJob In jobs
            ' Как в Python: чашка использует stiajka.parameters.depth,
            ' а не depth_parameter из блока Chashka stiajki.
            AddHoles(job.Cups, SettingParameter("diameter", "Стяжка_D"),
                     SettingParameter("depth", "Стяжка_h"), Direction(cup),
                     Text(cup, "feature_name", "Stiajka cup"), job.Owner)
            OptionalDisplay("Скрытие первого эскиза", Sub() job.Sketch1.Visible = False)
            OptionalDisplay("Скрытие второго эскиза", Sub() job.Sketch2.Visible = False)
        Next
    End Sub
End Class
