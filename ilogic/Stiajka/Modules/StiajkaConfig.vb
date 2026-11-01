' Straight VB code. Shared part of ThisRule; do not run separately.
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
    Private Sub LoadConfig()
        ' Настройки iLogic автономны. Имена ниже — параметры открытой детали.
        ' Диаметры и глубины вычисляет Inventor; числовые значения здесь не дублируются.
        st = New Dictionary(Of String, Object) From {
            {"parameters", New Dictionary(Of String, Object) From {
                {"diameter", "Стяжка_D"}, {"depth", "Стяжкаh_резьбаШтока_Петля"}, {"offset", "Стяжка_отступ"}}},
            {"Otv_stijki_v_torec", HoleSettings("Стяжка_D_телаШтока", "Стяжка_отступ", "positive", "Stiajka outer 8x34")},
            {"Otv_stijki_v_bokoviny", HoleSettings("Стяжка_D_резьбыШтока", "Стяжкаh_резьбаШтока_Петля", "negative", "Stiajka outer 5x13")},
            {"shkant_v_plast", HoleSettings("Шкант_D", "Шкант_глубина_в_пласть", "negative", "Shkant 8x10")},
            {"shkant_v_torets", HoleSettings("Шкант_D", "Шкант_глубина_в_торец", "positive", "Shkant 8x20")},
            {"Chashka stiajki", New Dictionary(Of String, Object) From {
                {"diameter_parameter", "Стяжка_D"}, {"depth_parameter", "Стяжка_отступ"},
                {"direction", "positive"}, {"feature_name", "Stiajka cup"}}}}
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

    Private Function SettingParameter(key As String, fallback As String) As String
        Return ResolveName(Text(Block(st, "parameters"), key, fallback))
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
