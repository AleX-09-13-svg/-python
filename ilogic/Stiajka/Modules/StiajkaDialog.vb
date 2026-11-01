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
            dialog.AutoScaleMode = AutoScaleMode.None
            dialog.Width = 900 : dialog.Height = Math.Min(613, Screen.FromPoint(Cursor.Position).WorkingArea.Height)
            dialog.Font = New System.Drawing.Font("Segoe UI", 10.0F)
            dialog.FormBorderStyle = FormBorderStyle.FixedDialog
            dialog.StartPosition = FormStartPosition.CenterScreen
            dialog.MaximizeBox = False : dialog.MinimizeBox = False
            dialog.TopMost = True
            Dim fields As New TableLayoutPanel With {.Dock = DockStyle.Top, .AutoSize = True,
                .AutoSizeMode = AutoSizeMode.GrowAndShrink, .ColumnCount = 1, .RowCount = 2,
                .Padding = New Padding(16), .Margin = New Padding(0)}
            fields.ColumnStyles.Add(New ColumnStyle(SizeType.Percent, 100.0F))
            fields.RowStyles.Add(New RowStyle(SizeType.AutoSize))
            fields.RowStyles.Add(New RowStyle(SizeType.AutoSize))
            Dim label As New Label With {.AutoSize = True, .Text = OffsetDialogLabel,
                .Margin = New Padding(0, 0, 0, 8)}
            Dim combo As New ComboBox With {.Dock = DockStyle.Top, .Margin = New Padding(0, 0, 0, 24),
                .DropDownWidth = 1000, .DropDownHeight = 1280, .IntegralHeight = False, .DropDownStyle = ComboBoxStyle.DropDownList}
            fields.Controls.Add(label, 0, 0) : fields.Controls.Add(combo, 0, 1)
            dialog.Controls.Add(fields)
            combo.Items.AddRange(options.ToArray())
            If combo.Items.Count > 0 Then combo.SelectedIndex = 0
            Dim preferred As String = "Минимальный_отступ_присадки_от_кромки_Каркас"
            If combo.Items.Contains(preferred) Then combo.SelectedItem = preferred
            Dim load As New Button With {.AutoSize = True, .AutoSizeMode = AutoSizeMode.GrowAndShrink,
                .MinimumSize = New System.Drawing.Size(280, 40),
                .Padding = New Padding(12, 6, 12, 6), .Margin = New Padding(0, 0, 0, 12),
                .Anchor = AnchorStyles.Left, .Text = "Загрузить параметры модели"}
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
            Dim ok As New Button With {.AutoSize = True, .AutoSizeMode = AutoSizeMode.GrowAndShrink,
                .MinimumSize = New System.Drawing.Size(90, 36), .Padding = New Padding(12, 6, 12, 6),
                .Margin = New Padding(0, 0, 12, 0), .Text = "OK", .DialogResult = DialogResult.OK}
            Dim cancel As New Button With {.AutoSize = True, .AutoSizeMode = AutoSizeMode.GrowAndShrink,
                .MinimumSize = New System.Drawing.Size(90, 36), .Padding = New Padding(12, 6, 12, 6),
                .Margin = New Padding(0), .Text = "Отмена", .DialogResult = DialogResult.Cancel}
            ' Две строки: длинная подпись загрузки не конкурирует с OK и Отмена.
            Dim actions As New FlowLayoutPanel With {.AutoSize = True,
                .AutoSizeMode = AutoSizeMode.GrowAndShrink, .Dock = DockStyle.Fill,
                .FlowDirection = FlowDirection.RightToLeft, .WrapContents = False, .Margin = New Padding(0)}
            actions.Controls.Add(cancel) : actions.Controls.Add(ok)
            Dim footer As New TableLayoutPanel With {.Dock = DockStyle.Bottom, .AutoSize = True,
                .AutoSizeMode = AutoSizeMode.GrowAndShrink, .ColumnCount = 1, .RowCount = 2,
                .Padding = New Padding(16), .Margin = New Padding(0)}
            footer.ColumnStyles.Add(New ColumnStyle(SizeType.Percent, 100.0F))
            footer.RowStyles.Add(New RowStyle(SizeType.AutoSize))
            footer.RowStyles.Add(New RowStyle(SizeType.AutoSize))
            footer.Controls.Add(load, 0, 0) : footer.Controls.Add(actions, 0, 1)
            Dim layout As New TableLayoutPanel With {.Dock = DockStyle.Fill, .ColumnCount = 1, .RowCount = 3,
                .Margin = New Padding(0), .Padding = New Padding(0)}
            layout.ColumnStyles.Add(New ColumnStyle(SizeType.Percent, 100.0F))
            layout.RowStyles.Add(New RowStyle(SizeType.AutoSize))
            layout.RowStyles.Add(New RowStyle(SizeType.Percent, 100.0F))
            layout.RowStyles.Add(New RowStyle(SizeType.AutoSize))
            footer.Dock = DockStyle.Fill
            layout.Controls.Add(fields, 0, 0) : layout.Controls.Add(footer, 0, 2)
            dialog.Controls.Add(layout)
            dialog.MinimumSize = New System.Drawing.Size(500,
                fields.GetPreferredSize(New System.Drawing.Size(500, 0)).Height +
                footer.GetPreferredSize(New System.Drawing.Size(500, 0)).Height + 60)
            dialog.AcceptButton = ok : dialog.CancelButton = cancel
            If dialog.ShowDialog() <> DialogResult.OK OrElse combo.SelectedItem Is Nothing Then Return Nothing
            Return CStr(combo.SelectedItem)
        End Using
    End Function
End Class
