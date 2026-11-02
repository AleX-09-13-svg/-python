"""Проверить VB.NET и сигнатуры API правила без запуска модели Inventor."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
RULE = ROOT / "ilogic" / "Stiajka" / "Stiajka_2_inch_fixCentr.iLogicVb"


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
                Return New System.Web.Script.Serialization.JavaScriptSerializer().Serialize(result)
            End Using
        End Using
    End Function
'''


PETLI_SMOKE_METHOD = '''
    Private Function ValidationSegments(width As Double, height As Double, rotated As Boolean) As List(Of XY())
        Dim corners As XY() = {New XY(0, 0), New XY(width, 0), New XY(width, height), New XY(0, height)}
        Dim result As New List(Of XY())
        For i As Integer = 0 To 3
            result.Add(New XY() {ValidationTransform(corners(i), rotated), ValidationTransform(corners((i + 1) Mod 4), rotated)})
        Next
        Return result
    End Function

    Private Function ValidationTransform(p As XY, rotated As Boolean) As XY
        If Not rotated Then Return p
        Return New XY(p.X * 0.6 - p.Y * 0.8 + 13, p.X * 0.8 + p.Y * 0.6 - 9)
    End Function

    Private Function ValidationReject(action As Action) As Boolean
        Try
            action()
            Return False
        Catch
            Return True
        End Try
    End Function

    Public Function ValidationSnapshot() As String
        Dim result As New Dictionary(Of String, Object)
        Dim counts As New List(Of Integer)
        For Each height As Double In New Double() {999.999, 1000, 1599.999, 1600, 1999.999, 2000, 2500}
            counts.Add(HingeCount(height))
        Next
        result("counts") = counts
        Dim cases As New List(Of Object)
        For Each height As Double In New Double() {90, 100, 120, 160, 200, 240}
            For Each sideX As Double In New Double() {-1, 61}
                For Each rotated As Boolean In New Boolean() {False, True}
                    Dim segments As List(Of XY()) = ValidationSegments(60, height, rotated)
                    Dim origin As XY = ValidationTransform(New XY(sideX, 0), rotated)
                    Dim direction As XY = If(rotated, New XY(-0.8, 0.6), New XY(0, 1))
                    Dim f As Frame = RectangleFrame(segments, origin, direction)
                    Dim positions As Double() = FacadePositions(f, 3.5, 0.2)
                    Dim cups As New List(Of Double()), pilots As New List(Of Double())
                    For Each t As Double In positions
                        Dim center As XY = f.At(t, 2.2)
                        cups.Add(New Double() {center.X, center.Y})
                        For Each sign As Double In New Double() {-1, 1}
                            Dim pilot As XY = f.At(t + sign * 2.25, 3.15)
                            pilots.Add(New Double() {pilot.X, pilot.Y})
                        Next
                    Next
                    Dim projected As New List(Of XY) From {ValidationTransform(New XY(sideX, 15), rotated), ValidationTransform(New XY(sideX, height - 15), rotated)}
                    Dim rows As List(Of SideRow) = SideRows(f, projected, 0.2)
                    Dim sidePoints As New List(Of Double())
                    For Each row As SideRow In rows
                        sidePoints.Add(New Double() {row.First.X, row.First.Y})
                        sidePoints.Add(New Double() {row.Last.X, row.Last.Y})
                    Next
                    cases.Add(New Dictionary(Of String, Object) From {
                        {"height", height}, {"sideX", sideX}, {"rotated", rotated}, {"positions", positions},
                        {"cups", cups}, {"pilots", pilots}, {"sidePoints", sidePoints}, {"edge", f.Index}})
                Next
            Next
        Next
        result("cases") = cases
        Dim standard As Frame = RectangleFrame(ValidationSegments(60, 180, False), New XY(-1, 0), New XY(0, 1))
        Dim narrow As Frame = RectangleFrame(ValidationSegments(5.2, 180, False), New XY(-1, 0), New XY(0, 1))
        Dim shortFace As Frame = RectangleFrame(ValidationSegments(60, 20, False), New XY(-1, 0), New XY(0, 1))
        result("ambiguousRejected") = ValidationReject(Sub() RectangleFrame(ValidationSegments(60, 180, False), New XY(30, 0), New XY(0, 1)))
        result("shortRejected") = ValidationReject(Sub() FacadePositions(shortFace, 3.5, 0.2))
        result("pilotOverlapRejected") = ValidationReject(Sub() FacadePositions(standard, 3.5, 2))
        result("sideDepthRejected") = ValidationReject(Sub() SideRows(narrow, New List(Of XY) From {New XY(-1, 15)}, 0.2))
        result("sideOverlapRejected") = ValidationReject(Sub() SideRows(standard, New List(Of XY) From {New XY(-1, 15), New XY(-1, 15.1)}, 0.2))
        result("sideHeightRejected") = ValidationReject(Sub() SideRows(standard, New List(Of XY) From {New XY(-1, 0.05)}, 0.2))
        Return New System.Web.Script.Serialization.JavaScriptSerializer().Serialize(result)
    End Function
'''


CONFIRMAT_SMOKE_METHOD = '''
    Public Function ValidationSnapshot() As String
        Using memory As New System.IO.MemoryStream()
            Using writer As New System.IO.StreamWriter(memory)
                log = writer
                LoadConfig()
                Dim result As New Dictionary(Of String, Object)
                For Each key As String In New String() {"outer_2pcs", "inner_2pcs"}
                    For Each field As String In New String() {"diameter", "depth"}
                        result(key & "." & field) = ResolveExpression(Text(Block(st, key), field, ""))
                    Next
                Next
                layoutCount = 2
                result("twoPositions") = PointPositions(60.7, 5)
                result("span32") = PointSpan(13.2, 5)
                result("span64") = PointSpan(12, 2)
                result("spanLong") = PointSpan(40, 5)
                Dim rejected As Boolean = False
                Try
                    PointSpan(8, 3)
                Catch
                    rejected = True
                End Try
                result("shortRejected") = rejected
                rejected = False
                Try
                    layoutCount = 5
                    PointPositions(29.2, 5)
                Catch
                    rejected = True
                End Try
                result("overlapRejected") = rejected
                result("fivePositions") = PointPositions(60.7, 5)
                result("fiveReverse") = PointPositions(60.7, 5, False)
                result("exactMiddle") = PointPositions(61.2, 5)(2)
                result("anchorLeft") = AnchorByDistances(1, 50)
                result("anchorRight") = AnchorByDistances(50, 1)
                result("edgeDistance") = SegmentDistance(0, 2, 1.6, 0, 0, 0, 0, 4, 0)
                result("reverseEdgeDistance") = SegmentDistance(0, 2, 1.6, 0, 4, 0, 0, 0, 0)
                rejected = False
                Try
                    AnchorByDistances(5, 5)
                Catch
                    rejected = True
                End Try
                result("ambiguousAnchorRejected") = rejected
                rejected = False
                Try
                    PointPositions(32.4, 5)
                Catch
                    rejected = True
                End Try
                result("middleCollisionRejected") = rejected
                OptionalDisplay("color test", Sub()
                    Throw New System.Runtime.InteropServices.COMException("E_FAIL test", -2147467259)
                End Sub)
                result("displayErrorIgnored") = True
                Return New System.Web.Script.Serialization.JavaScriptSerializer().Serialize(result)
            End Using
        End Using
    End Function
'''


def smoke_check(output, interop, four=False, one=False, confirmat=False, petli=False, three=False, fixed_two=False):
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
    if petli:
        check_petli_snapshot(snapshot)
        return
    if confirmat:
        for key in ("outer_2pcs", "inner_2pcs"):
            expected = ("M_Конфирмат_D_вПласть", "M_Конфирмат_сквозное_отв") if key.startswith("outer") else ("M_Конфирмат_D_вТорец", "M_Конфирмат_длина")
            for field, value in zip(("diameter", "depth"), expected):
                assert snapshot[key + "." + field] == value, (key, field)
        assert abs(snapshot["span64"] - 6.4) < 1e-9
        assert abs(snapshot["spanLong"] - 28.8) < 1e-9
        assert snapshot["shortRejected"] and snapshot["overlapRejected"]
        assert abs(snapshot["span32"] - 3.2) < 1e-9
        two = snapshot["twoPositions"]
        assert len(two) == 2 and abs(two[0] + 24) < 1e-9 and abs(two[1] - 24) < 1e-9
        assert (60.7 - (two[1] - two[0])) / 2 >= 5
        five = snapshot["fivePositions"]
        assert len(five) == 5 and abs(five[2] + 2.95) < 1e-9
        assert abs(five[0] + 25.35) < 1e-9 and abs(five[-1] - 25.35) < 1e-9
        assert abs(five[1] - five[0] - 9.6) < 1e-9
        assert abs(five[-1] - five[-2] - 9.6) < 1e-9
        assert abs(five[2] - five[0] - 22.4) < 1e-9
        assert all(abs(a + b) < 1e-9 for a, b in zip(five, reversed(snapshot["fiveReverse"])))
        assert abs(snapshot["exactMiddle"]) < 1e-9
        assert snapshot["anchorLeft"] is True and snapshot["anchorRight"] is False
        assert abs(snapshot["edgeDistance"] - 1.6) < 1e-9
        assert abs(snapshot["reverseEdgeDistance"] - 1.6) < 1e-9
        assert snapshot["ambiguousAnchorRejected"] and snapshot["middleCollisionRejected"]
        assert snapshot["displayErrorIgnored"]
        print("Confirmat 2/5 layouts, built-in settings, grid spacing and overlap checks OK; no configuration files read. No Inventor model was run.")
        return
    expected = {"diameter": "Стяжка_D", "depth": "Стяжкаh_резьбаШтока_Петля", "offset": "Стяжка_отступ"}
    for key, diameter, depth, direction in (
        ("Otv_stijki_v_torec", "Стяжка_D_телаШтока", "Стяжка_отступ", 20993),
        ("Otv_stijki_v_bokoviny", "Стяжка_D_резьбыШтока", "Стяжкаh_резьбаШтока_Петля", 20994),
        ("shkant_v_plast", "Шкант_D", "Шкант_глубина_в_пласть", 20994),
        ("shkant_v_torets", "Шкант_D", "Шкант_глубина_в_торец", 20993),
    ):
        expected[key + ".diameter"] = diameter
        expected[key + ".depth"] = depth
        expected[key + ".direction"] = direction
    expected["cup.direction"] = 20993
    for name, value in expected.items():
        if snapshot.get(name) != value:
            raise AssertionError(f"Built-in settings mismatch: {name}: {snapshot.get(name)!r} != {value!r}")
    if one:
        assert snapshot["centers"] == [-1.6, 1.6]
        assert snapshot["edgeRejected"] is True
        assert snapshot["overlapRejected"] is True
    elif three:
        from stiajka.three_geometry import three_tie_span
        import math
        span = three_tie_span(60.7, 5.05)
        pitch = math.floor(span / 2 / 3.2) * 3.2
        ties, dowels = snapshot["ties"], snapshot["dowels"]
        assert len(ties) == 3 and len(dowels) == 4
        for actual, expected in zip(ties, (-span / 2, -span / 2 + pitch, span / 2)):
            assert abs(actual - expected) < 1e-9
        assert abs((ties[1] - ties[0]) / 3.2 - round((ties[1] - ties[0]) / 3.2)) < 1e-9
        assert 0 <= -ties[1] < 3.2
        reverse = snapshot["reverseTies"]
        assert all(abs(a + b) < 1e-9 for a, b in zip(ties, reversed(reverse)))
        assert abs(snapshot["exactPitch"] - 25.6) < 1e-9
        assert snapshot["offsetOptions"] == ["CustomOffset", "CustomThickness"]
        assert snapshot["referenceStart"] is True and snapshot["referenceEnd"] is False
        assert snapshot["ambiguousReferenceRejected"]
        assert snapshot["axisAnchors"] == [True, False, False, True]
        assert abs(60.7 / 2 + ties[0] - 5.05) < 1e-9
        assert abs(60.7 / 2 - ties[2] - 5.05) < 1e-9
        assert abs(dowels[0] - ties[0] - 3.2) < 1e-9
        assert abs(ties[2] - dowels[1] - 3.2) < 1e-9
        for actual, shift in zip(dowels[2:], (-3.2, 3.2)):
            assert abs(actual - ties[1] - shift) < 1e-9
        assert all(abs(a + b) < 1e-9 for a, b in zip(sorted(dowels), reversed(sorted(snapshot["reverseDowels"]))))
        assert snapshot["centralOverlapRejected"]
        assert snapshot["overlapRejected"] is True
    elif four:
        assert abs(snapshot["spanLong"] - 30) < 1e-9
        ties = snapshot["ties"]
        dowels = snapshot["dowels"]
        assert len(ties) == len(dowels) == 4
        assert abs(ties[0] + 25) < 1e-9 and abs(ties[-1] - 25) < 1e-9
        assert abs(ties[1] - ties[0] - 16) < 1e-9
        assert abs(ties[3] - ties[2] - 16) < 1e-9
        assert abs(ties[2] - ties[1] - 18) < 1e-9
        assert abs(snapshot["exactOuterPitch"] - 19.2) < 1e-9
        assert snapshot["roundedShortRejected"]
        for i in range(4):
            assert abs(abs(dowels[i] - ties[i]) - 3.2) < 1e-9
            assert abs(dowels[i] + dowels[3 - i]) < 1e-9
        assert snapshot["overlapRejected"] is True
    elif fixed_two:
        assert abs(snapshot["span64"] - 8) < 1e-9
        assert abs(snapshot["spanLong"] - 30) < 1e-9
        assert abs(snapshot["fixedSpan"] - 50.6) < 1e-9
        assert abs((60.7 - snapshot["fixedSpan"]) / 2 - 5.05) < 1e-9
        assert abs(snapshot["minimumSpan"] - 6.4) < 1e-9
    else:
        assert abs(snapshot["span64"] - 6.4) < 1e-9
        assert abs(snapshot["spanLong"] - 28.8) < 1e-9
    assert snapshot["shortRejected"] is True
    assert snapshot["normalPerpendicular"] == 1.0
    assert snapshot["normalParallel"] == 0.0
    assert snapshot["normalOpposite"] == 0.0
    assert snapshot["displayErrorIgnored"] is True
    print("Built-in settings, spacing and short-face validation OK; no configuration files read. No Inventor model was run.")


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


def check_petli_snapshot(snapshot):
    from petli.layout import calculate_layout, hinge_count, pilot_positions, side_hole_rows

    def close(actual, expected):
        if isinstance(expected, (list, tuple)):
            assert len(actual) == len(expected), (actual, expected)
            for a, b in zip(actual, expected):
                close(a, b)
        else:
            assert abs(actual - expected) < 1e-8, (actual, expected)

    assert snapshot["counts"] == [hinge_count(h) for h in (999.999, 1000, 1599.999, 1600, 1999.999, 2000, 2500)]
    assert len(snapshot["cases"]) == 24
    for case in snapshot["cases"]:
        height, side_x, rotated = case["height"], case["sideX"], case["rotated"]

        def transform(p):
            x, y = p
            return (x * .6 - y * .8 + 13, x * .8 + y * .6 - 9) if rotated else p

        corners = [(0, 0), (60, 0), (60, height), (0, height)]
        segments = [(transform(corners[i]), transform(corners[(i + 1) % 4])) for i in range(4)]
        frame = calculate_layout(segments, transform((side_x, 0)), (-.8, .6) if rotated else (0, 1), 3.5)

        def at(t, offset):
            return tuple(frame.start[i] + frame.along[i] * t + frame.inward[i] * offset for i in range(2))

        assert case["edge"] == frame.edge_index
        close(case["positions"], frame.distances)
        close(case["cups"], [at(t, 2.2) for t in frame.distances])
        close(case["pilots"], [at(t, offset) for t, offset in pilot_positions(frame, 3.5, .2)])
        rows = side_hole_rows(frame, [transform((side_x, t)) for t in (15, height - 15)], .2)
        close(case["sidePoints"], [p for row in rows for p in row[1:]])
    for key in ("ambiguousRejected", "shortRejected", "pilotOverlapRejected", "sideDepthRejected",
                "sideOverlapRejected", "sideHeightRejected"):
        assert snapshot[key], key
    print("Petli matches Python in 24 layouts: cups, pilots, side holes, thresholds and 6 invalid cases. No Inventor model was run.")


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
    if re.search(r'(?i)\.json|Deserialize|ReadAllText|ReadAllBytes', combined):
        parser.error("Правила iLogic должны работать без чтения файлов конфигурации.")
    four = "Private Const TieCount As Integer = 4" in combined
    three = "Private Const TieCount As Integer = 3" in combined
    fixed_two = "Private Const FixedEdgeLayout As Boolean = True" in combined
    one = "Private Const TieCount As Integer = 1" in combined
    confirmat = 'Private Const Workflow As String = "confirmat"' in combined
    if confirmat:
        # Без этой ссылки внешний компилятор проходил проверку за счёт
        # /reference ниже, хотя iLogic не видел типы из подключённых модулей.
        rule_header = args.rule.read_text(encoding="utf-8-sig")
        if not re.search(r'(?im)^\s*AddReference\s+"Autodesk\.Inventor\.Interop(?:\.dll)?"\s*$', rule_header):
            parser.error("Главное правило Confirmat должно явно подключать Autodesk.Inventor.Interop.dll через AddReference.")
    petli = 'Private Const Workflow As String = "petli"' in combined
    # ThisApplication предоставляет iLogic. Для проверки вне iLogic нужна
    # только декларация свойства; сам Inventor и документ не запускаются.
    source = "Imports System\n" + source.replace(
        "Public Class ThisRule",
        "Public Class ThisRule\n    Public Property ThisApplication As Inventor.Application", 1,
    )
    if args.smoke:
        method = PETLI_SMOKE_METHOD if petli else CONFIRMAT_SMOKE_METHOD if confirmat else SMOKE_METHOD
        if fixed_two:
            method = method.replace('result("spanLong") = PointSpan(40, 5)', '''
                result("spanLong") = PointSpan(40, 5)
                result("fixedSpan") = PointSpan(60.7, 5.05)
                result("minimumSpan") = PointSpan(10.4, 2)
            ''')
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
                result("exactOuterPitch") = OuterPitch(57.6)
                Dim roundedShort As Boolean = False
                Try
                    PointSpan(31, 5)
                Catch
                    roundedShort = True
                End Try
                result("roundedShortRejected") = roundedShort
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
        if three:
            method = method.replace('result("span64") = PointSpan(12, 2)', '''
                Dim ties() As Double = TiePositions(60.7, 5.05)
                Dim dowels() As Double = DowelPositions(ties)
                result("ties") = ties
                result("dowels") = dowels
                result("reverseTies") = TiePositions(60.7, 5.05, False)
                result("exactPitch") = MiddlePitch(51.2)
                result("referenceStart") = ChooseAnchorAtStart(1, 50)
                result("referenceEnd") = ChooseAnchorAtStart(50, 1)
                result("axisAnchors") = New Boolean() {AnchorForAxis(True, 1), AnchorForAxis(True, -1),
                    AnchorForAxis(False, 1), AnchorForAxis(False, -1)}
                Dim ambiguousReference As Boolean = False
                Try
                    ChooseAnchorAtStart(5, 5)
                Catch
                    ambiguousReference = True
                End Try
                result("ambiguousReferenceRejected") = ambiguousReference
                result("offsetOptions") = OffsetParameterNames(New String() {"CustomOffset", "CustomThickness"})
                ValidateClearance(ties, dowels, 0.8, 0.8, 1.5)
                Dim reverse() As Double = TiePositions(60.7, 5.05, False)
                result("reverseDowels") = DowelPositions(reverse)
                ValidateClearance(reverse, DowelPositions(reverse), 0.8, 0.8, 1.5)
                Dim centralOverlap As Boolean = False
                Try
                    Dim shortTies() As Double = TiePositions(22.4, 2)
                    ValidateClearance(shortTies, DowelPositions(shortTies), 0.8, 0.8, 1.5)
                Catch
                    centralOverlap = True
                End Try
                result("centralOverlapRejected") = centralOverlap
                Dim overlapRejected As Boolean = False
                Try
                    ties = TiePositions(10.5, 2)
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
                smoke_check(output, interop, four, one, confirmat, petli, three=three, fixed_two=fixed_two)
        return result.returncode
    finally:
        for check in checks:
            check.unlink(missing_ok=True)
        if output is not None:
            output.unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
