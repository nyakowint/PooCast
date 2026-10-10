param([ValidateSet('Inspect', 'Refresh', 'Quit', 'Screenshot')][string]$Action = 'Inspect')
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class FlooValidationNative {
    [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr hwnd, IntPtr dc, uint flags);
    [DllImport("user32.dll")] public static extern IntPtr SendMessage(IntPtr hwnd, uint msg, IntPtr wp, IntPtr lp);
}
'@
$condition = [System.Windows.Automation.PropertyCondition]::new(
    [System.Windows.Automation.AutomationElement]::NameProperty, 'FlooCast')
$window = [System.Windows.Automation.AutomationElement]::RootElement.FindFirst(
    [System.Windows.Automation.TreeScope]::Children, $condition)
if (-not $window) { throw 'FlooCast window is not available.' }
$elements = $window.FindAll([System.Windows.Automation.TreeScope]::Descendants,
    [System.Windows.Automation.Condition]::TrueCondition)
if ($Action -eq 'Screenshot') {
    Add-Type -AssemblyName System.Drawing
    $rect = $window.Current.BoundingRectangle
    $bitmap = [System.Drawing.Bitmap]::new([int]$rect.Width, [int]$rect.Height)
    $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
    $dc = $graphics.GetHdc()
    try {
        if (-not [FlooValidationNative]::PrintWindow($window.Current.NativeWindowHandle, $dc, 0)) {
            throw 'PrintWindow failed.'
        }
    } finally { $graphics.ReleaseHdc($dc) }
    $bitmap.Save((Join-Path $PSScriptRoot 'validation-window.png'))
    $graphics.Dispose()
    $bitmap.Dispose()
    return
}
foreach ($element in $elements) {
    $name = $element.Current.Name
    if ($Action -eq 'Inspect' -and $name) {
        $state = ''
        if ($element.Current.ControlType -in @([System.Windows.Automation.ControlType]::CheckBox,
                [System.Windows.Automation.ControlType]::RadioButton)) {
            $state = ' Checked=' + [FlooValidationNative]::SendMessage(
                $element.Current.NativeWindowHandle, 0x00F0, [IntPtr]::Zero, [IntPtr]::Zero)
        }
        $pattern = $null
        if ($element.TryGetCurrentPattern([System.Windows.Automation.TogglePattern]::Pattern, [ref]$pattern)) {
            $state = ' Toggle=' + $pattern.Current.ToggleState
        }
        $pattern = $null
        if ($element.TryGetCurrentPattern([System.Windows.Automation.SelectionItemPattern]::Pattern, [ref]$pattern)) {
            $state += ' Selected=' + $pattern.Current.IsSelected
        }
        Write-Output ($name + ' Enabled=' + $element.Current.IsEnabled + $state)
    }
    if (($Action -eq 'Refresh' -and $name -eq 'Refresh') -or
        ($Action -eq 'Quit' -and $name -eq 'Quit App')) {
        $null = [FlooValidationNative]::SendMessage($element.Current.NativeWindowHandle,
            0x00F5, [IntPtr]::Zero, [IntPtr]::Zero)
        Write-Output ('Invoked ' + $name)
        return
    }
}
if ($Action -ne 'Inspect') { throw "Control for $Action not found." }
