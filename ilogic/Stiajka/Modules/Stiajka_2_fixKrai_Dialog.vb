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
        Dim names As New List(Of String)
        For Each parameter As UserParameter In comp.Parameters.UserParameters
            names.Add(parameter.Name)
        Next
        Dim options As List(Of String) = OffsetParameterNames(names)
        Using dialog As New Form()
            dialog.Text = OffsetDialogTitle
            dialog.AutoScaleMode = AutoScaleMode.None
            dialog.Width = 700 : dialog.Height = Math.Min(260, Screen.FromPoint(Cursor.Position).WorkingArea.Height)
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
            Dim value As New ComboBox With {.Dock = DockStyle.Top, .DropDownStyle = ComboBoxStyle.DropDownList,
                .DropDownWidth = 1000, .Margin = New Padding(0, 0, 0, 24)}
            value.Items.AddRange(options.ToArray())
            If value.Items.Count > 0 Then value.SelectedIndex = 0
            fields.Controls.Add(label, 0, 0) : fields.Controls.Add(value, 0, 1)
            dialog.Controls.Add(fields)
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
            AddHandler dialog.Shown, Sub(sender As Object, e As EventArgs)
                value.Focus()
            End Sub
            If dialog.ShowDialog() <> DialogResult.OK OrElse value.SelectedItem Is Nothing Then Return Nothing
            Return CStr(value.SelectedItem)
        End Using
    End Function

    Private Function OffsetParameterNames(names As IEnumerable(Of String)) As List(Of String)
        Dim sorted As New List(Of String)(names)
        sorted.Sort(StringComparer.CurrentCulture)
        Dim result As New List(Of String)
        For Each name As String In sorted
            If name.IndexOf("отступ", StringComparison.OrdinalIgnoreCase) >= 0 AndAlso Not result.Contains(name) Then result.Add(name)
        Next
        For Each name As String In sorted
            If Not result.Contains(name) Then result.Add(name)
        Next
        Return result
    End Function
End Class
