"""Проверить VB.NET и сигнатуры API правила без запуска модели Inventor."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
RULE = ROOT / "ilogic" / "Stiajka" / "Stiajka_2_inch.iLogicVb"


SMOKE_METHOD = '''
    Public Function ValidationSnapshot() As String
        Using memory As New System.IO.MemoryStream()
            Using writer As New System.IO.StreamWriter(memory)
                log = writer
                LoadConfig()
                Dim result As New Dictionary(Of String, Object)
                For Each key As String In New String() {"offset", "diameter", "depth"}
                    result(key) = SettingParameter(key, "")
                Next
                For Each key As String In New String() {"Otv_stijki_v_torec", "Otv_stijki_v_bokoviny", "shkant_v_plast", "shkant_v_torets"}
                    Dim values As Dictionary(Of String, Object) = Block(st, key)
                    result(key & ".diameter") = ResolveExpression(Text(values, "diameter", ""))
                    result(key & ".depth") = ResolveExpression(Text(values, "depth", ""))
                    result(key & ".direction") = CInt(Direction(values))
                Next
                result("cup.direction") = CInt(Direction(Block(st, "Chashka stiajki")))
                result("span64") = PointSpan(12, 2)
                result("spanLong") = PointSpan(40, 5)
                result("normalPerpendicular") = NormalsCrossLengthSquared(1, 0, 0, 0, 1, 0)
                result("normalParallel") = NormalsCrossLengthSquared(1, 0, 0, 1, 0, 0)
                result("normalOpposite") = NormalsCrossLengthSquared(1, 0, 0, -1, 0, 0)
                OptionalDisplay("проверка отказа цвета", Sub()
                    Throw New System.Runtime.InteropServices.COMException("E_FAIL test", -2147467259)
                End Sub)
                result("displayErrorIgnored") = True
                Dim rejected As Boolean = False
                Try
                    PointSpan(8, 3)
                Catch
                    rejected = True
                End Try
                result("shortRejected") = rejected
                Return New JavaScriptSerializer().Serialize(result)
            End Using
        End Using
    End Function
'''


CONFIRMAT_SMOKE_METHOD = '''
    Public Function ValidationSnapshot() As String
        Using memory As New System.IO.MemoryStream()
            Using writer As New System.IO.StreamWriter(memory)
                log = writer
                LoadConfig()
                Dim result As New Dictionary(Of String, Object)
                For Each key As String In New String() {"outer_2pcs", "inner_2pcs", "outer_3pcs", "inner_3pcs"}
                    For Each field As String In New String() {"diameter", "depth"}
                        result(key & "." & field) = ResolveExpression(Text(Block(st, key), field, ""))
                    Next
                Next
                result("span64") = PointSpan(12, 2)
                result("spanLong") = PointSpan(40, 5)
                result("count2") = ConfirmatCount(2)
                result("count3") = ConfirmatCount(3)
                Dim rejected As Boolean = False
                Try
                    PointSpan(8, 3)
                Catch
                    rejected = True
                End Try
                result("shortRejected") = rejected
                rejected = False
                Try
                    ConfirmatCount(2.5)
                Catch
                    rejected = True
                End Try
                result("invalidCountRejected") = rejected
                result("unitlessKeep") = CountKeepExpression("count", "ul")
                result("lengthKeep") = CountKeepExpression("count", "mm")
                OptionalDisplay("color test", Sub()
                    Throw New System.Runtime.InteropServices.COMException("E_FAIL test", -2147467259)
                End Sub)
                result("displayErrorIgnored") = True
                Return New JavaScriptSerializer().Serialize(result)
            End Using
        End Using
    End Function
'''


def smoke_check(output, interop, four=False, one=False, confirmat=False):
    def literal(path):
        return "'" + str(path).replace("'", "''") + "'"

    command = "\n".join([
        "$ErrorActionPreference = 'Stop'",
        "[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)",
        "Add-Type -AssemblyName System.Web.Extensions",
        "[void][System.Reflection.Assembly]::LoadFrom(" + literal(interop) + ")",
        "$assembly = [System.Reflection.Assembly]::LoadFrom(" + literal(output) + ")",
        "$rule = $assembly.CreateInstance('ThisRule')",
        "[Console]::WriteLine($rule.ValidationSnapshot())",
    ])
    result = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],
                            capture_output=True, encoding="utf-8", errors="replace")
    if result.returncode:
        raise RuntimeError(result.stderr or result.stdout)
    snapshot = json.loads(result.stdout.strip().lstrip("\ufeff"))
    sys.path.insert(0, str(ROOT))
    from common.settings import load_settings
    if confirmat:
        settings = load_settings()["confirmat"]
        for key in ("outer_2pcs", "inner_2pcs", "outer_3pcs", "inner_3pcs"):
            for field in ("diameter", "depth"):
                assert snapshot[key + "." + field] == settings[key][field], (key, field)
        assert abs(snapshot["span64"] - 6.4) < 1e-9
        assert abs(snapshot["spanLong"] - 28.8) < 1e-9
        assert snapshot["count2"] == 2 and snapshot["count3"] == 3
        assert snapshot["shortRejected"] and snapshot["invalidCountRejected"]
        assert snapshot["unitlessKeep"] == "count * 0"
        assert snapshot["lengthKeep"] == "(count / (1 mm)) * 0"
        assert snapshot["displayErrorIgnored"]
        print("Confirmat settings match Python; spacing, count and Keep expressions OK. No Inventor model was run.")
        return
    settings = load_settings()["stiajka"]
    expected = dict(settings["parameters"])
    for key in ("Otv_stijki_v_torec", "Otv_stijki_v_bokoviny", "shkant_v_plast", "shkant_v_torets"):
        expected[key + ".diameter"] = settings[key]["diameter"]
        expected[key + ".depth"] = settings[key]["depth"]
        expected[key + ".direction"] = 20994 if settings[key]["direction"] == "negative" else 20993
    expected["cup.direction"] = 20994 if settings["Chashka stiajki"]["direction"] == "negative" else 20993
    for name, value in expected.items():
        if snapshot.get(name) != value:
            raise AssertionError(f"Native/Python settings mismatch: {name}: {snapshot.get(name)!r} != {value!r}")
    if one:
        assert snapshot["centers"] == [-1.6, 1.6]
        assert snapshot["edgeRejected"] is True
        assert snapshot["overlapRejected"] is True
    elif four:
        assert abs(snapshot["spanLong"] - 30) < 1e-9
        ties = snapshot["ties"]
        dowels = snapshot["dowels"]
        assert len(ties) == len(dowels) == 4
        assert abs(ties[0] + 25) < 1e-9 and abs(ties[-1] - 25) < 1e-9
        for i in range(3):
            assert abs(ties[i + 1] - ties[i] - 50 / 3) < 1e-9
        for i in range(4):
            assert abs(abs(dowels[i] - ties[i]) - 3.2) < 1e-9
            assert abs(dowels[i] + dowels[3 - i]) < 1e-9
        assert snapshot["overlapRejected"] is True
    else:
        assert abs(snapshot["span64"] - 6.4) < 1e-9
        assert abs(snapshot["spanLong"] - 28.8) < 1e-9
    assert snapshot["shortRejected"] is True
    assert snapshot["normalPerpendicular"] == 1.0
    assert snapshot["normalParallel"] == 0.0
    assert snapshot["normalOpposite"] == 0.0
    assert snapshot["displayErrorIgnored"] is True
    print("Native JSON/settings match Python; spacing and short-face validation OK. No Inventor model was run.")


def read_rule_sources(rule):
    """Resolve AddVbFile beside each source for standalone compiler validation.

    Inventor's external-rule search folders must still be configured separately.
    Each file remains a separate compilation unit, preserving its Imports scope.
    """
    sources = {}

    def visit(path):
        path = path.resolve()
        if path in sources:
            return
        lines = path.read_text(encoding="utf-8-sig").splitlines()
        sources[path] = ""
        code = []
        for line in lines:
            match = re.fullmatch(r'\s*AddVbFile\s+"([^"]+)"\s*', line, re.IGNORECASE)
            if match:
                visit(path.parent / match.group(1))
            elif not line.lstrip().lower().startswith("addreference "):
                code.append(line)
        sources[path] = "\n".join(code)

    visit(rule)
    return list(sources.values())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rule", type=Path, default=RULE)
    parser.add_argument("--inventor-dir", type=Path,
                        default=Path("C:/Program Files/Autodesk/Inventor 2023"))
    parser.add_argument("--smoke", action="store_true", help="Проверить настройки и расчёты в .NET без запуска модели.")
    args = parser.parse_args()
    framework = Path("C:/Windows/Microsoft.NET/Framework64/v4.0.30319")
    compiler = framework / "vbc.exe"
    interop = args.inventor_dir / "Bin" / "Public Assemblies" / "Autodesk.Inventor.Interop.dll"
    if not compiler.exists() or not interop.exists():
        parser.error("Нужны Windows, компилятор .NET Framework и Autodesk.Inventor.Interop.dll.")
    sources = read_rule_sources(args.rule)
    source = sources[0]
    combined = "\n".join(sources)
    four = "Private Const TieCount As Integer = 4" in combined
    one = "Private Const TieCount As Integer = 1" in combined
    confirmat = 'Private Const Workflow As String = "confirmat"' in combined
    # ThisApplication предоставляет iLogic. Для проверки вне iLogic нужна
    # только декларация свойства; сам Inventor и документ не запускаются.
    source = "Imports System\n" + source.replace(
        "Public Class ThisRule",
        "Public Class ThisRule\n    Public Property ThisApplication As Inventor.Application", 1,
    )
    if args.smoke:
        method = CONFIRMAT_SMOKE_METHOD if confirmat else SMOKE_METHOD
        if one:
            method = method.replace('result("span64") = PointSpan(12, 2)', '''
                result("centers") = CenterPositions(12)
                ValidateCenterClearance(12, 0.8, 0.8, 1.5)
                Dim edgeRejected As Boolean = False
                Try
                    ValidateCenterClearance(4.5, 0.8, 0.8, 1.5)
                Catch
                    edgeRejected = True
                End Try
                result("edgeRejected") = edgeRejected
                Dim overlapRejected As Boolean = False
                Try
                    ValidateCenterClearance(12, 4, 4, 1.5)
                Catch
                    overlapRejected = True
                End Try
                result("overlapRejected") = overlapRejected
            ''').replace('result("spanLong") = PointSpan(40, 5)', '')
            method = method.replace('PointSpan(8, 3)', 'CenterPositions(3.2)')
        if four:
            method = method.replace('result("span64") = PointSpan(12, 2)', '''
                Dim ties() As Double = TiePositions(60, 5)
                Dim dowels() As Double = DowelPositions(ties)
                result("ties") = ties
                result("dowels") = dowels
                ValidateClearance(ties, dowels, 0.8, 0.8, 1.5)
                Dim overlapRejected As Boolean = False
                Try
                    ties = TiePositions(25, 2)
                    ValidateClearance(ties, DowelPositions(ties), 0.8, 0.8, 1.5)
                Catch
                    overlapRejected = True
                End Try
                result("overlapRejected") = overlapRejected
            ''')
        source = source.replace("    Public Sub Main()", method + "\n    Public Sub Main()", 1)
    sources[0] = source
    checks = []
    output = None
    try:
        for code in sources:
            with tempfile.NamedTemporaryFile(dir=ROOT / "tests", prefix="_native_check_",
                                             suffix=".vb", delete=False) as file:
                check = Path(file.name)
            checks.append(check)
            check.write_text(code, encoding="utf-8-sig")
        output = checks[0].with_suffix(".dll")
        refs = [interop] + [framework / name for name in (
            "System.dll", "System.Core.dll", "System.Web.Extensions.dll",
            "System.Drawing.dll", "System.Windows.Forms.dll",
        )]
        command = [str(compiler), "/nologo", "/utf8output", "/target:library",
                   "/optionexplicit+", "/optioninfer+", "/optionstrict-", "/out:" + str(output)]
        command += ["/reference:" + str(ref) for ref in refs]
        result = subprocess.run(command + [str(check) for check in checks], capture_output=True, encoding="utf-8", errors="replace")
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        if result.returncode == 0:
            print("VB.NET compilation OK against " + str(interop))
            if args.smoke:
                smoke_check(output, interop, four, one, confirmat)
        return result.returncode
    finally:
        for check in checks:
            check.unlink(missing_ok=True)
        if output is not None:
            output.unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
