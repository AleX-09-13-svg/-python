' Straight VB code. Part of the Confirmat rule; do not run separately.
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
        ' Настройки iLogic автономны. Имена ниже — параметры открытой детали.
        ' Диаметры и глубины вычисляет Inventor; числовые значения здесь не дублируются.
        st = New Dictionary(Of String, Object) From {
            {"outer_2pcs", HoleSettings("M_Конфирмат_D_вПласть", "M_Конфирмат_сквозное_отв", "positive", "Confirmat 2pcs counterbore")},
            {"inner_2pcs", HoleSettings("M_Конфирмат_D_вТорец", "M_Конфирмат_длина", "positive", "Confirmat 2pcs inner")},
            {"outer_3pcs", HoleSettings("M_Конфирмат_D_вПласть", "M_Конфирмат_сквозное_отв", "positive", "Confirmat counterbore")},
            {"inner_3pcs", HoleSettings("M_Конфирмат_D_вТорец", "M_Конфирмат_длина", "positive", "Confirmat inner")}}
        WriteLog("Настройки: встроенные в правило iLogic; размеры из параметров детали.")
    End Sub

    Private Function HoleSettings(diameter As String, depth As String, direction As String, featureName As String) As Dictionary(Of String, Object)
        Return New Dictionary(Of String, Object) From {
            {"diameter", diameter}, {"depth", depth}, {"direction", direction}, {"feature_name", featureName}}
    End Function

    Private Function ResolveName(name As String) As String
        Return name
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
