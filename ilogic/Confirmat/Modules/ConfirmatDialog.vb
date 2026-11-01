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
    Private Function ChooseParameters() As String()
        Dim names As New List(Of String)
        Dim loadNames As Action(Of Object) = Sub(collection As Object)
            For Each parameter As Inventor.Parameter In collection
                If Not names.Contains(parameter.Name) Then names.Add(parameter.Name)
            Next
            names.Sort(StringComparer.CurrentCulture)
        End Sub
        loadNames(comp.Parameters.UserParameters)
        Using dialog As New Form()
            dialog.Text = "02 Конфирмат — параметры присадки"
            dialog.Width = 900 : dialog.Height = 460
            dialog.Font = New System.Drawing.Font("Segoe UI", 10.0F)
            dialog.FormBorderStyle = FormBorderStyle.FixedDialog
            dialog.StartPosition = FormStartPosition.CenterScreen
            dialog.MaximizeBox = False : dialog.MinimizeBox = False : dialog.TopMost = True
            Dim labels() As String = {"Толщина материала:", "Отступ от кромки:", "Параметр количества (2 или 3):"}
            Dim filters() As String = {"толщина", "отступ", "конфирмат"}
            Dim defaults() As String = {"Толщина_каркаса_МДФ", "Минимальный_отступ_присадки_от_кромки_Каркас", "Количество_конфирматов"}
            Dim combos As New List(Of ComboBox)
            For i As Integer = 0 To 2
                Dim label As New Label With {.Left = 16, .Top = 16 + i * 86, .Width = 852, .Height = 26, .Text = labels(i)}
                Dim combo As New ComboBox With {.Left = 16, .Top = 46 + i * 86, .Width = 852, .DropDownWidth = 1000, .DropDownHeight = 280, .IntegralHeight = False, .DropDownStyle = ComboBoxStyle.DropDown}
                combos.Add(combo)
                dialog.Controls.Add(label) : dialog.Controls.Add(combo)
            Next
            Dim populate As Action = Sub()
                For i As Integer = 0 To 2
                    Dim current As String = combos(i).Text
                    combos(i).Items.Clear()
                    For Each name As String In names
                        Dim lower As String = name.ToLowerInvariant()
                        If lower.Contains(filters(i)) OrElse (i = 2 AndAlso lower.Contains("кол")) Then combos(i).Items.Add(name)
                    Next
                    If current <> "" Then
                        combos(i).Text = current
                    ElseIf combos(i).Items.Contains(defaults(i)) Then
                        combos(i).SelectedItem = defaults(i)
                    ElseIf combos(i).Items.Count > 0 Then
                        combos(i).SelectedIndex = 0
                    Else
                        combos(i).Text = defaults(i)
                    End If
                Next
            End Sub
            populate()
            Dim load As New Button With {.Left = 16, .Top = 320, .Width = 310, .Height = 36, .Text = "Загрузить параметры модели"}
            AddHandler load.Click, Sub(sender As Object, e As EventArgs)
                load.Enabled = False
                loadNames(comp.Parameters.ModelParameters)
                populate()
            End Sub
            Dim ok As New Button With {.Left = 640, .Top = 320, .Width = 100, .Height = 36, .Text = "OK", .DialogResult = DialogResult.OK}
            Dim cancel As New Button With {.Left = 756, .Top = 320, .Width = 112, .Height = 36, .Text = "Отмена", .DialogResult = DialogResult.Cancel}
            dialog.Controls.AddRange(New Control() {load, ok, cancel})
            dialog.AcceptButton = ok : dialog.CancelButton = cancel
            If dialog.ShowDialog() <> DialogResult.OK Then Return Nothing
            Dim result As New List(Of String)
            For Each combo As ComboBox In combos
                If combo.Text.Trim() = "" Then Throw New Exception("Выберите все три параметра.")
                result.Add(ResolveName(combo.Text.Trim()))
            Next
            Return result.ToArray()
        End Using
    End Function
End Class
