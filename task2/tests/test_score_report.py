"""score_report のテスト。

集計値は課題で配布された 課題2.csv の実データを手計算した値で確かめる。
入出力は tmp_path に書いた CSV と capsys で受け取る。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import score_report  # noqa: E402
from score_report import Record, Stats  # noqa: E402

HEADER = "名前,日付,科目,スコア\n"


def write_csv(tmp_path: Path, body: str, *, name: str = "t.csv", encoding: str = "utf-8") -> Path:
    path = tmp_path / name
    path.write_text(HEADER + body, encoding=encoding)
    return path


class Test表示幅:
    """全角は2桁を占める。文字数で詰めると表が崩れる。"""

    def test_半角は1桁(self):
        assert score_report.display_width("abc12") == 5

    def test_全角は2桁(self):
        assert score_report.display_width("山田太郎") == 8

    def test_混在(self):
        assert score_report.display_width("名前A") == 5

    def test_空文字は0(self):
        assert score_report.display_width("") == 0

    def test_左寄せは表示幅で詰める(self):
        assert score_report.pad("山田", 8) == "山田" + " " * 4

    def test_右寄せは表示幅で詰める(self):
        assert score_report.pad("山田", 8, align_right=True) == " " * 4 + "山田"

    def test_幅を超えるときは切らない(self):
        assert score_report.pad("山田太郎", 4) == "山田太郎"


class Test表組み:
    """期待する出力を直接書く。

    display_width で測って「全行が同じ幅」と確かめる書き方だと、
    display_width が壊れたときにテスト側も同じように壊れて通ってしまう。
    実装を使わずに検証するため、正しい桁数を空白の数で固定する。
    """

    def test_全角が混じっても桁が揃う(self):
        table = score_report.render_table(
            ["名前", "件数"],
            [["山田太郎", "8"], ["A", "10"]],
        )
        # 「山田太郎」が8桁、「件数」が4桁なので列幅は 8 と 4 になる
        assert table == "\n".join(
            [
                "名前    " "  " "件数",
                "--------" "  " "----",
                "山田太郎" "  " "   8",
                "A       " "  " "  10",
            ]
        )

    def test_見出しのほうが長い列でも崩れない(self):
        table = score_report.render_table(["参加者名", "点"], [["A", "1"]])

        assert table == "\n".join(
            [
                "参加者名" "  " "点",
                "--------" "  " "--",
                "A       " "  " " 1",
            ]
        )

    def test_区切り線が入る(self):
        table = score_report.render_table(["名前"], [["A"]])
        assert table.splitlines()[1].strip("- ") == ""


class TestStats:
    def test_平均は合計と件数から出す(self):
        assert Stats(count=4, total=10, highest=4, lowest=1).average == 2.5

    def test_スコアを足しても元のStatsは変わらない(self):
        original = Stats.of(80)
        added = original.merged_with(90)

        assert original == Stats(count=1, total=80, highest=80, lowest=80)
        assert added == Stats(count=2, total=170, highest=90, lowest=80)

    def test_書き換えられない(self):
        with pytest.raises(Exception):
            Stats.of(80).count = 5  # type: ignore[misc]


class Test読み込み:
    def test_正常な行を読む(self, tmp_path):
        path = write_csv(tmp_path, "山田,2024-09-01,数学,80\n")
        records, skipped = score_report.load_records(path)

        assert records == [Record("山田", "2024-09-01", "数学", 80)]
        assert skipped == []

    def test_BOM付きでも列を見失わない(self, tmp_path):
        path = write_csv(tmp_path, "山田,2024-09-01,数学,80\n", encoding="utf-8-sig")
        records, _ = score_report.load_records(path)

        assert records[0].name == "山田"

    def test_前後の空白は落とす(self, tmp_path):
        path = write_csv(tmp_path, " 山田 ,2024-09-01,数学, 80 \n")
        records, _ = score_report.load_records(path)

        assert records == [Record("山田", "2024-09-01", "数学", 80)]

    def test_区切りだけの行は理由付きで飛ばす(self, tmp_path):
        path = write_csv(tmp_path, "山田,2024-09-01,数学,80\n,,,\n")
        records, skipped = score_report.load_records(path)

        assert len(records) == 1
        assert [s.reason for s in skipped] == ["空行"]

    def test_完全な空行はcsvモジュールが先に捨てるので報告に出ない(self, tmp_path):
        """報告できない行が1種類あることを明示しておく。

        csv.DictReader は中身が何も無い行を自分で読み飛ばす。
        「報告されなかった＝正常な行だった」と読まれないよう、
        この振る舞いをテストで固定する。
        """
        path = write_csv(tmp_path, "山田,2024-09-01,数学,80\n\n鈴木,2024-09-02,英語,90\n")
        records, skipped = score_report.load_records(path)

        assert len(records) == 2
        assert skipped == []

    def test_非数値のスコアは理由付きで飛ばす(self, tmp_path):
        path = write_csv(tmp_path, "山田,2024-09-01,数学,満点\n")
        records, skipped = score_report.load_records(path)

        assert records == []
        assert "数値ではない" in skipped[0].reason
        assert "満点" in skipped[0].reason

    def test_欠損は空の列名を理由に出す(self, tmp_path):
        path = write_csv(tmp_path, ",2024-09-01,数学,80\n")
        _, skipped = score_report.load_records(path)

        assert skipped[0].reason == "名前 が空"

    def test_飛ばした行の行番号はヘッダーを数えた実際の行番号(self, tmp_path):
        path = write_csv(tmp_path, "山田,2024-09-01,数学,80\n山田,2024-09-01,数学,x\n")
        _, skipped = score_report.load_records(path)

        assert skipped[0].line == 3

    def test_必要な列が無ければ列名を挙げて失敗する(self, tmp_path):
        path = tmp_path / "t.csv"
        path.write_text("名前,点数\n山田,80\n", encoding="utf-8")

        with pytest.raises(ValueError) as e:
            score_report.load_records(path)

        assert "日付" in str(e.value)
        assert "科目" in str(e.value)
        assert "スコア" in str(e.value)

    def test_空ファイルは失敗する(self, tmp_path):
        path = tmp_path / "t.csv"
        path.write_text("", encoding="utf-8")

        with pytest.raises(ValueError):
            score_report.load_records(path)


class Test集計:
    def test_初出順に並ぶ(self):
        records = [
            Record("B", "d", "s", 1),
            Record("A", "d", "s", 2),
            Record("B", "d", "s", 3),
        ]
        assert list(score_report.summarize(records, lambda r: r.name)) == ["B", "A"]

    def test_同じ人のスコアがまとまる(self):
        records = [Record("A", "d", "数学", 70), Record("A", "d", "英語", 90)]
        stats = score_report.summarize(records, lambda r: r.name)["A"]

        assert (stats.count, stats.average, stats.highest, stats.lowest) == (2, 80.0, 90, 70)


class Test配布データ:
    """課題で配布された 課題2.csv の実データで確かめる。"""

    @pytest.fixture
    def records(self):
        records, skipped = score_report.load_records(score_report.DEFAULT_CSV)
        assert skipped == []
        return records

    def test_40件ある(self, records):
        assert len(records) == 40

    @pytest.mark.parametrize(
        "name, count, average, highest, lowest",
        [
            ("山田太郎", 8, 83.625, 91, 75),
            ("鈴木花子", 8, 88.625, 94, 80),
            ("佐藤次郎", 8, 73.125, 80, 65),
            ("田中一郎", 8, 87.5, 92, 83),
            ("高橋花子", 8, 92.0, 96, 88),
        ],
    )
    def test_参加者ごとの平均_最高_最低(self, records, name, count, average, highest, lowest):
        stats = score_report.summarize(records, lambda r: r.name)[name]

        assert stats.count == count
        assert stats.average == pytest.approx(average)
        assert stats.highest == highest
        assert stats.lowest == lowest

    @pytest.mark.parametrize(
        "subject, count, total, highest, lowest",
        [
            ("数学", 10, 848, 95, 70),
            ("英語", 10, 867, 93, 78),
            ("国語", 10, 837, 94, 65),
            ("理科", 5, 422, 96, 72),
            ("社会", 5, 425, 90, 68),
        ],
    )
    def test_科目ごとの集計(self, records, subject, count, total, highest, lowest):
        stats = score_report.summarize(records, lambda r: r.subject)[subject]

        assert (stats.count, stats.total, stats.highest, stats.lowest) == (
            count,
            total,
            highest,
            lowest,
        )

    def test_全体の合計は参加者ごとの合計と一致する(self, records):
        per_person = score_report.summarize(records, lambda r: r.name)
        per_subject = score_report.summarize(records, lambda r: r.subject)

        assert sum(s.total for s in per_person.values()) == 3399
        assert sum(s.total for s in per_subject.values()) == 3399

    def test_全体サマリー(self, records):
        summary = score_report.overall_summary(records)

        assert "参加者 5 人 / 40 件" in summary
        assert "平均 85.0" in summary
        assert "最高 96（高橋花子・理科・2024-09-03）" in summary
        assert "最低 65（佐藤次郎・国語・2024-09-01）" in summary


class Testレポート:
    def test_読み飛ばしが無ければその節を出さない(self):
        report = score_report.build_report([Record("A", "d", "s", 80)], [])
        assert "読み飛ばした行" not in report

    def test_読み飛ばしがあれば件数と理由を出す(self):
        report = score_report.build_report(
            [Record("A", "d", "s", 80)],
            [score_report.SkippedRow(line=5, reason="空行")],
        )
        assert "読み飛ばした行（1 件）" in report
        assert "5 行目: 空行" in report


class TestCLI:
    def test_引数なしで配布データを集計して0を返す(self, capsys):
        assert score_report.main([]) == 0

        out = capsys.readouterr().out
        assert "参加者ごとの成績" in out
        assert "科目ごとの成績" in out
        assert "山田太郎" in out

    def test_ファイルが無ければ1を返して標準エラーに出す(self, capsys, tmp_path):
        assert score_report.main([str(tmp_path / "none.csv")]) == 1

        captured = capsys.readouterr()
        assert "見つかりません" in captured.err
        assert captured.out == ""

    def test_列が足りなければ1を返す(self, capsys, tmp_path):
        path = tmp_path / "t.csv"
        path.write_text("名前\nA\n", encoding="utf-8")

        assert score_report.main([str(path)]) == 1
        assert "エラー" in capsys.readouterr().err

    def test_使える行が1件も無ければ1を返す(self, capsys, tmp_path):
        path = write_csv(tmp_path, "山田,2024-09-01,数学,満点\n")

        assert score_report.main([str(path)]) == 1
        assert "1件もありません" in capsys.readouterr().err
