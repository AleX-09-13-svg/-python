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
    Private Function ChooseOffset() As String
        Dim options As New List(Of String)
        Dim loadNames As Action(Of Object) = Sub(parameters As Object)
            For Each parameter As Inventor.Parameter In parameters
                If parameter.Name.IndexOf("отступ", StringComparison.OrdinalIgnoreCase) >= 0 AndAlso Not options.Contains(parameter.Name) Then options.Add(parameter.Name)
            Next
            options.Sort(StringComparer.CurrentCulture)
        End Sub
        Dim watch As Stopwatch = Stopwatch.StartNew()
        loadNames(comp.Parameters.UserParameters)
        WriteLog("Чтение пользовательских параметров: " & Seconds(watch) & "s")
        Using dialog As New Form()
            dialog.Text = OffsetDialogTitle
            dialog.Width = 900 : dialog.Height = 460
            dialog.Font = New System.Drawing.Font("Segoe UI", 10.0F)
            dialog.FormBorderStyle = FormBorderStyle.FixedDialog
            dialog.StartPosition = FormStartPosition.CenterScreen
            dialog.MaximizeBox = False : dialog.MinimizeBox = False
            dialog.TopMost = True
            Dim label As New Label With {.Left = 16, .Top = 16, .Width = 852, .Height = 26, .Text = OffsetDialogLabel}
            Dim combo As New ComboBox With {.Left = 16, .Top = 52, .Width = 852, .DropDownWidth = 1000, .DropDownHeight = 320, .IntegralHeight = False, .DropDownStyle = ComboBoxStyle.DropDownList}
            combo.Items.AddRange(options.ToArray())
            If combo.Items.Count > 0 Then combo.SelectedIndex = 0
            Dim preferred As String = "Минимальный_отступ_присадки_от_кромки_Каркас"
            If combo.Items.Contains(preferred) Then combo.SelectedItem = preferred
            Dim load As New Button With {.Left = 16, .Top = 115, .Width = 310, .Height = 36, .Text = "Загрузить параметры модели"}
            AddHandler load.Click, Sub(sender As Object, e As EventArgs)
                Dim current As String = CStr(combo.SelectedItem)
                Dim timer As Stopwatch = Stopwatch.StartNew()
                loadNames(comp.Parameters.ModelParameters)
                combo.Items.Clear() : combo.Items.AddRange(options.ToArray())
                If current IsNot Nothing AndAlso combo.Items.Contains(current) Then
                    combo.SelectedItem = current
                ElseIf combo.Items.Count > 0 Then
                    combo.SelectedIndex = 0
                End If
                load.Enabled = False
                WriteLog("Чтение параметров модели: " & Seconds(timer) & "s")
            End Sub
            Dim ok As New Button With {.Left = 640, .Top = 115, .Width = 100, .Height = 36, .Text = "OK", .DialogResult = DialogResult.OK}
            Dim cancel As New Button With {.Left = 756, .Top = 115, .Width = 112, .Height = 36, .Text = "Отмена", .DialogResult = DialogResult.Cancel}
            dialog.Controls.AddRange(New Control() {label, combo, load, ok, cancel})
            dialog.AcceptButton = ok : dialog.CancelButton = cancel
            If dialog.ShowDialog() <> DialogResult.OK OrElse combo.SelectedItem Is Nothing Then Return Nothing
            Return CStr(combo.SelectedItem)
        End Using
    End Function
End Class
