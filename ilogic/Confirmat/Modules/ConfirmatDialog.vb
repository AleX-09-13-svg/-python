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
            dialog.Text = "02 Конфирмат — " & layoutCount.ToString() & " шт."
            dialog.AutoScaleMode = AutoScaleMode.None
            dialog.Width = 900 : dialog.Height = Math.Min(613, Screen.FromPoint(Cursor.Position).WorkingArea.Height)
            dialog.Font = New System.Drawing.Font("Segoe UI", 10.0F)
            dialog.FormBorderStyle = FormBorderStyle.FixedDialog
            dialog.StartPosition = FormStartPosition.CenterScreen
            dialog.MaximizeBox = False : dialog.MinimizeBox = False : dialog.TopMost = True
            Dim labels() As String = {"Пользовательский параметр толщины материала:",
                If(layoutCount = 2, "Пользовательский параметр минимального отступа от края до центра:",
                   "Пользовательский параметр точного отступа от края до ближайшего центра:")}
            Dim filters() As String = {"толщина", "отступ"}
            Dim defaults() As String = {"Толщина_каркаса_МДФ", "Минимальный_отступ_присадки_от_кромки_Каркас"}
            Dim combos As New List(Of ComboBox)
            Dim fields As New TableLayoutPanel With {.Dock = DockStyle.Top, .AutoSize = True,
                .AutoSizeMode = AutoSizeMode.GrowAndShrink, .ColumnCount = 1, .RowCount = 5,
                .Padding = New Padding(16), .Margin = New Padding(0)}
            fields.ColumnStyles.Add(New ColumnStyle(SizeType.Percent, 100.0F))
            dialog.Controls.Add(fields)
            For i As Integer = 0 To 1
                fields.RowStyles.Add(New RowStyle(SizeType.AutoSize))
                fields.RowStyles.Add(New RowStyle(SizeType.AutoSize))
                Dim label As New Label With {.AutoSize = True, .Text = labels(i),
                    .Margin = New Padding(0, 0, 0, 8)}
                Dim combo As New ComboBox With {.Dock = DockStyle.Top, .Margin = New Padding(0, 0, 0, 24),
                    .DropDownWidth = 1000, .DropDownHeight = 1120, .IntegralHeight = False, .DropDownStyle = ComboBoxStyle.DropDownList}
                combos.Add(combo)
                fields.Controls.Add(label, 0, i * 2)
                fields.Controls.Add(combo, 0, i * 2 + 1)
            Next
            fields.RowStyles.Add(New RowStyle(SizeType.AutoSize))
            fields.Controls.Add(New Label With {.AutoSize = True, .Margin = New Padding(0, 0, 0, 12),
                .Text = If(layoutCount = 2,
                    "Два центра симметрично. Расстояние кратно 32 мм; отступ не меньше выбранного.",
                    "Две пары по 96 мм; средний — по сетке 32 мм от стороны выбранной кромки.")}, 0, 4)
            Dim populate As Action = Sub()
                For i As Integer = 0 To 1
                    Dim current As String = combos(i).Text
                    combos(i).Items.Clear()
                    For Each name As String In names
                        Dim lower As String = name.ToLowerInvariant()
                        If lower.Contains(filters(i)) Then combos(i).Items.Add(name)
                    Next
                    For Each name As String In names
                        If Not combos(i).Items.Contains(name) Then combos(i).Items.Add(name)
                    Next
                    If current <> "" Then
                        combos(i).Text = current
                    ElseIf combos(i).Items.Contains(defaults(i)) Then
                        combos(i).SelectedItem = defaults(i)
                    ElseIf combos(i).Items.Count > 0 Then
                        combos(i).SelectedIndex = 0
                    End If
                Next
            End Sub
            populate()
            Dim ok As New Button With {.AutoSize = True, .AutoSizeMode = AutoSizeMode.GrowAndShrink,
                .MinimumSize = New System.Drawing.Size(90, 36), .Padding = New Padding(12, 6, 12, 6),
                .Margin = New Padding(0, 0, 12, 0), .Text = "OK", .DialogResult = DialogResult.OK}
            Dim cancel As New Button With {.AutoSize = True, .AutoSizeMode = AutoSizeMode.GrowAndShrink,
                .MinimumSize = New System.Drawing.Size(90, 36), .Padding = New Padding(12, 6, 12, 6),
                .Margin = New Padding(0), .Text = "Отмена", .DialogResult = DialogResult.Cancel}
            Dim actions As New FlowLayoutPanel With {.AutoSize = True,
                .AutoSizeMode = AutoSizeMode.GrowAndShrink, .Dock = DockStyle.Fill,
                .FlowDirection = FlowDirection.RightToLeft, .WrapContents = False, .Margin = New Padding(0)}
            actions.Controls.Add(cancel) : actions.Controls.Add(ok)
            Dim footer As New TableLayoutPanel With {.Dock = DockStyle.Bottom, .AutoSize = True,
                .AutoSizeMode = AutoSizeMode.GrowAndShrink, .ColumnCount = 1, .RowCount = 1,
                .Padding = New Padding(16), .Margin = New Padding(0)}
            footer.ColumnStyles.Add(New ColumnStyle(SizeType.Percent, 100.0F))
            footer.RowStyles.Add(New RowStyle(SizeType.AutoSize))
            footer.Controls.Add(actions, 0, 0)
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
            If dialog.ShowDialog() <> DialogResult.OK Then Return Nothing
            Dim result As New List(Of String)
            For Each combo As ComboBox In combos
                If Not names.Contains(combo.Text.Trim()) Then Throw New Exception("Выберите оба пользовательских параметра.")
                result.Add(combo.Text.Trim())
            Next
            Return result.ToArray()
        End Using
    End Function
End Class
