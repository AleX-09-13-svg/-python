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
    Private Function ConfirmatCount(value As Double) As Integer
        If value = 2 OrElse value = 3 Then Return CInt(value)
        Throw New Exception("Параметр количества конфирматов должен быть равен 2 или 3.")
    End Function

    Private Function RequiredParameters(thickness As String, edgeOffset As String) As List(Of String)
        Dim result As New List(Of String) From {thickness, edgeOffset}
        For Each key As String In New String() {"outer_2pcs", "inner_2pcs", "outer_3pcs", "inner_3pcs"}
            For Each field As String In New String() {"diameter", "depth"}
                Dim expression As String = Text(Block(st, key), field, "")
                If expression = "" Then Throw New Exception("Нет настройки confirmat." & key & "." & field)
                Dim name As String = ResolveName(expression)
                If Regex.IsMatch(name, "^[^\W\d]\w*$") AndAlso Not result.Contains(name) Then result.Add(name)
            Next
        Next
        Return result
    End Function

    Private Sub EnsureCountKeep(source As Inventor.Parameter)
        Dim units As String = CStr(source.Units).Trim()
        If units.ToLowerInvariant() = "text" OrElse units.ToLowerInvariant() = "boolean" Then Throw New Exception("Количество должно быть числовым параметром.")
        Dim expression As String = CountKeepExpression(source.Name, units)
        Dim parameter As Inventor.Parameter = Nothing
        Try
            parameter = comp.Parameters.Item("Keep_Excel_Params_Unitless")
        Catch
        End Try
        If parameter Is Nothing Then
            comp.Parameters.UserParameters.AddByExpression("Keep_Excel_Params_Unitless", expression, UnitsTypeEnum.kUnitlessUnits)
        ElseIf Regex.Replace(parameter.Expression, "\s+", "") <> Regex.Replace(expression, "\s+", "") Then
            parameter.Expression = expression
        End If
    End Sub

    Private Function CountKeepExpression(name As String, units As String) As String
        If units = "" OrElse units.ToLowerInvariant() = "ul" Then Return name & " * 0"
        Return "(" & name & " / (1 " & units & ")) * 0"
    End Function

    Private Sub LoadConfig()
        Dim serializer As New JavaScriptSerializer()
        config = New Dictionary(Of String, Object)
        Dim local As String = System.IO.Path.Combine(ProjectRoot, "settings.json")
        If System.IO.File.Exists(local) Then config = serializer.Deserialize(Of Dictionary(Of String, Object))(System.IO.File.ReadAllText(local, Encoding.UTF8))
        Dim library As String = System.IO.Path.GetFullPath(System.IO.Path.Combine(ProjectRoot, "..", "01_inventor_service", "service", "excel_parameters", "part_config.example.json"))
        If System.IO.File.Exists(library) Then
            Merge(config, serializer.Deserialize(Of Dictionary(Of String, Object))(System.IO.File.ReadAllText(library, Encoding.UTF8)))
        ElseIf config.Count = 0 Then
            Throw New Exception("Не найден файл настроек: " & library)
        End If
        nameMap = New Dictionary(Of String, String)
        If config.ContainsKey("linked_parameters") Then
            For Each item As Object In DirectCast(config("linked_parameters"), System.Collections.IEnumerable)
                Dim row As Dictionary(Of String, Object) = DirectCast(item, Dictionary(Of String, Object))
                Dim key As String = Text(row, "name", "")
                If key <> "" Then nameMap(key) = Text(row, "source_name", key)
            Next
        End If
        st = Block(config, Workflow)
        WriteLog("Настройки: " & If(System.IO.File.Exists(library), library, local))
    End Sub

    Private Sub Merge(target As Dictionary(Of String, Object), source As Dictionary(Of String, Object))
        For Each entry As KeyValuePair(Of String, Object) In source
            If target.ContainsKey(entry.Key) AndAlso TypeOf target(entry.Key) Is Dictionary(Of String, Object) AndAlso TypeOf entry.Value Is Dictionary(Of String, Object) Then
                Merge(DirectCast(target(entry.Key), Dictionary(Of String, Object)), DirectCast(entry.Value, Dictionary(Of String, Object)))
            Else
                target(entry.Key) = entry.Value
            End If
        Next
    End Sub

    Private Function ResolveName(name As String) As String
        Dim aliases As Dictionary(Of String, Object) = Block(config, "parameter_aliases")
        Dim resolved As String = Text(aliases, name, name)
        If nameMap.ContainsKey(resolved) Then Return nameMap(resolved)
        Return resolved
    End Function

    Private Function ResolveExpression(expression As String) As String
        Return Regex.Replace(expression, "[^\W\d]\w*", Function(m As Match) ResolveName(m.Value))
    End Function

    Private Sub EnsureKeep(names As List(Of String))
        Dim terms As New List(Of String)
        For Each name As String In names
            terms.Add(name & " * 0")
        Next
        Dim expression As String = String.Join(" + ", terms.ToArray())
        Dim parameter As Inventor.Parameter = Nothing
        Try
            parameter = comp.Parameters.Item("Keep_Excel_Params")
        Catch
        End Try
        If parameter Is Nothing Then
            comp.Parameters.UserParameters.AddByExpression("Keep_Excel_Params", expression, "mm")
        ElseIf Regex.Replace(parameter.Expression, "\s+", "") <> Regex.Replace(expression, "\s+", "") Then
            parameter.Expression = expression
        End If
    End Sub

    Private Function Block(parent As Dictionary(Of String, Object), key As String) As Dictionary(Of String, Object)
        If parent.ContainsKey(key) AndAlso TypeOf parent(key) Is Dictionary(Of String, Object) Then Return DirectCast(parent(key), Dictionary(Of String, Object))
        Return New Dictionary(Of String, Object)
    End Function

    Private Function Text(parent As Dictionary(Of String, Object), key As String, fallback As String) As String
        If parent.ContainsKey(key) AndAlso parent(key) IsNot Nothing Then Return Convert.ToString(parent(key), CultureInfo.InvariantCulture)
        Return fallback
    End Function
End Class
