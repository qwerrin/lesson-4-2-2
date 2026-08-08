"""score_charts のテスト。

課題3は「グラフを作って画像に保存する」課題なので、画像そのものは目で見るしかない。
そこで検証できるところを3層に分けている。

1. 集計値  … 配布された 課題3.csv を手計算した値で固定する（実装からは作らない）
2. 図の中身 … Figure を作った直後に Axes を読み、要件で求められた
              ラベル・パーセンテージ・軸ラベル・凡例が実際に載っているかを見る
3. 保存    … ファイルができて PNG として読める大きさになっているか

「日本語が □ になっていないか」は目視では見落とすので、描画時の
欠落グリフ警告を拾って0件であることを確かめる。
"""

from __future__ import annotations

import sys
import warnings
from pathlib import Path

import matplotlib
import pytest

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

sys.path.insert(0, str(Path(__file__).parent.parent))

import score_charts  # noqa: E402
from score_charts import Record, Stats  # noqa: E402

HEADER = "名前,所属,スコア\n"

# 配布された 課題3.csv を手で数えた値。実装を呼んで作らない。
# 所属ごとの人数と合計スコア（35 行を4グループに分けたもの）
EXPECTED_COUNTS = {"営業": 10, "開発": 10, "管理": 8, "人事": 7}
EXPECTED_TOTALS = {"営業": 830, "開発": 889, "管理": 697, "人事": 555}
EXPECTED_HIGHEST = {"営業": 93, "開発": 94, "管理": 95, "人事": 82}
EXPECTED_LOWEST = {"営業": 70, "開発": 82, "管理": 76, "人事": 75}
# 35 行を1グループとして足した合計。上の4グループの合計と一致しなければ行を落としている
EXPECTED_GRAND_TOTAL = 2971


def write_csv(tmp_path: Path, body: str, *, name: str = "t.csv", encoding: str = "utf-8") -> Path:
    path = tmp_path / name
    path.write_text(HEADER + body, encoding=encoding)
    return path


def collect_glyph_warnings(build) -> list[str]:
    """図を「組み立てるところから」実行して、欠落グリフの警告を集める。

    matplotlib は字が出せなくても例外を投げず、警告を出して □ を描く。
    画像は生成されるので、戻り値や例外を見ているだけでは気づけない。

    受け取るのが Figure ではなく組み立てる関数なのは、出来上がった図を
    後から draw() しても警告が出ないため。build_* の中の tight_layout() が
    文字幅を測る時点で警告は出きっており、そのあと測っても 0 件に見える。
    最初にこれを Figure で受け取る形で書いたせいで、フォント設定を丸ごと
    外しても3件とも素通りした（624 件の警告がテストの外で出ていた）。
    """
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        fig = build()
    plt.close(fig)
    return [str(w.message) for w in caught if "missing from font" in str(w.message)]


@pytest.fixture
def records():
    """配布 CSV をそのまま読んだレコード。"""
    return score_charts.load_records(score_charts.DEFAULT_CSV)[0]


class Test読み込み:
    def test_配布CSVを読める(self):
        rows, skipped = score_charts.load_records(score_charts.DEFAULT_CSV)
        assert len(rows) == 35
        assert skipped == []

    def test_先頭行の中身(self):
        rows, _ = score_charts.load_records(score_charts.DEFAULT_CSV)
        assert rows[0] == Record(name="佐藤", department="営業", score=85)

    def test_末尾行の中身(self):
        rows, _ = score_charts.load_records(score_charts.DEFAULT_CSV)
        assert rows[-1] == Record(name="松田", department="人事", score=81)

    def test_必要な列が無ければ理由つきで落ちる(self, tmp_path):
        path = tmp_path / "t.csv"
        path.write_text("名前,スコア\n佐藤,85\n", encoding="utf-8")
        with pytest.raises(ValueError, match="所属"):
            score_charts.load_records(path)

    def test_BOM付きでも読める(self, tmp_path):
        """Excel が保存した CSV には BOM が付き、utf-8 で開くと列名が変わる。"""
        path = write_csv(tmp_path, "佐藤,営業,85\n", encoding="utf-8-sig")
        rows, _ = score_charts.load_records(path)
        assert rows == [Record(name="佐藤", department="営業", score=85)]

    def test_スコアが数値でない行は理由つきで飛ばす(self, tmp_path):
        path = write_csv(tmp_path, "佐藤,営業,満点\n鈴木,開発,90\n")
        rows, skipped = score_charts.load_records(path)
        assert [r.name for r in rows] == ["鈴木"]
        assert len(skipped) == 1
        assert "満点" in skipped[0].reason

    def test_所属が空の行は理由つきで飛ばす(self, tmp_path):
        path = write_csv(tmp_path, "佐藤,,85\n")
        rows, skipped = score_charts.load_records(path)
        assert rows == []
        assert "所属" in skipped[0].reason


class Test集計:
    """期待値は配布 CSV を手で数えたもの。"""

    def test_所属ごとの人数(self, records):
        assert score_charts.count_by_department(records) == EXPECTED_COUNTS

    def test_人数の合計が全レコード数と一致する(self, records):
        counts = score_charts.count_by_department(records)
        assert sum(counts.values()) == len(records) == 35

    def test_所属ごとの合計スコア(self, records):
        stats = score_charts.stats_by_department(records)
        assert {k: s.total for k, s in stats.items()} == EXPECTED_TOTALS

    def test_所属ごとの最高点(self, records):
        stats = score_charts.stats_by_department(records)
        assert {k: s.highest for k, s in stats.items()} == EXPECTED_HIGHEST

    def test_所属ごとの最低点(self, records):
        stats = score_charts.stats_by_department(records)
        assert {k: s.lowest for k, s in stats.items()} == EXPECTED_LOWEST

    def test_所属ごとの平均(self, records):
        stats = score_charts.stats_by_department(records)
        assert stats["営業"].average == pytest.approx(83.0)
        assert stats["開発"].average == pytest.approx(88.9)
        assert stats["管理"].average == pytest.approx(87.125)
        assert stats["人事"].average == pytest.approx(555 / 7)

    def test_別のグループ分けでも合計が一致する(self, records):
        """4グループに分けた合計と、35 行を素直に足した合計を突き合わせる。

        どちらも同じ 35 行を別の足し方で集めているので、
        行を1つでも取りこぼしていれば一致しない。
        """
        by_department = sum(s.total for s in score_charts.stats_by_department(records).values())
        straight = sum(r.score for r in records)
        assert by_department == straight == EXPECTED_GRAND_TOTAL

    def test_所属の並びはCSVの初出順(self, records):
        assert list(score_charts.count_by_department(records)) == ["営業", "開発", "管理", "人事"]


class Testビン数:
    """ヒストグラムのビン数は「適切に」設定することが要件。

    値を直接書くとデータが変わったときに合わなくなるので、件数から計算する。
    期待値は 2 の冪で手計算できるものを選んでいる（実装の式を写さないため）。
    """

    def test_配布データは7ビン(self, records):
        assert score_charts.bin_count([r.score for r in records]) == 7

    @pytest.mark.parametrize(
        ("n", "expected"),
        [(1, 1), (2, 2), (4, 3), (8, 4), (16, 5), (32, 6), (33, 7), (35, 7)],
    )
    def test_件数から計算する(self, n, expected):
        assert score_charts.bin_count([80] * n) == expected

    def test_空なら落ちる(self):
        with pytest.raises(ValueError):
            score_charts.bin_count([])

    @pytest.mark.parametrize(("n", "expected_bins"), [(10, 5), (35, 7), (100, 8)])
    def test_ヒストグラムのビン数が件数で変わる(self, n, expected_bins):
        """図が定数ではなく bin_count を使って描かれていることを確かめる。

        件数を配布データの 35 だけで試すと、bin_count の結果も直書きの 7 も
        同じ値になり区別できない。実際 build_histogram の中を bins = 7 に
        書き換えても 48 件すべて通ってしまった。
        ビン数が変わる件数を混ぜて、初めて直書きが落ちるようになる。
        """
        scores = [70 + (i % 26) for i in range(n)]
        fig = score_charts.build_histogram(scores)
        assert len(fig.axes[0].patches) == expected_bins
        plt.close(fig)


class Test日本語フォント:
    """日本語が □ になる事故は例外にならない。警告を拾って落とす。"""

    def test_候補から実在するフォントを選ぶ(self):
        name = score_charts.use_japanese_font()
        assert name in score_charts.JAPANESE_FONT_CANDIDATES

    def test_選んだフォントがrcParamsに入る(self):
        name = score_charts.use_japanese_font()
        assert plt.rcParams["font.family"] == ["sans-serif"]
        assert plt.rcParams["font.sans-serif"][0] == name

    def test_候補が1つも無ければ落ちる(self, monkeypatch):
        monkeypatch.setattr(score_charts, "JAPANESE_FONT_CANDIDATES", ("実在しないフォント",))
        with pytest.raises(RuntimeError, match="日本語"):
            score_charts.use_japanese_font()

    def test_円グラフに欠落グリフが無い(self, records):
        counts = score_charts.count_by_department(records)
        assert collect_glyph_warnings(lambda: score_charts.build_pie(counts)) == []

    def test_棒グラフに欠落グリフが無い(self, records):
        stats = score_charts.stats_by_department(records)
        assert collect_glyph_warnings(lambda: score_charts.build_bar(stats)) == []

    def test_ヒストグラムに欠落グリフが無い(self, records):
        scores = [r.score for r in records]
        assert collect_glyph_warnings(lambda: score_charts.build_histogram(scores)) == []


class Test円グラフ:
    """要件: 所属ごとの内訳、各セクションにパーセンテージとラベル。"""

    def test_区画は所属の数だけある(self, records):
        fig = score_charts.build_pie(score_charts.count_by_department(records))
        assert len(fig.axes[0].patches) == 4
        plt.close(fig)

    def test_所属名がすべて載っている(self, records):
        fig = score_charts.build_pie(score_charts.count_by_department(records))
        texts = {t.get_text() for t in fig.axes[0].texts}
        assert {"営業", "開発", "管理", "人事"} <= texts
        plt.close(fig)

    def test_パーセンテージが載っている(self, records):
        """10/35=28.6% 8/35=22.9% 7/35=20.0%（小数第1位まで）。"""
        fig = score_charts.build_pie(score_charts.count_by_department(records))
        texts = {t.get_text() for t in fig.axes[0].texts}
        assert {"28.6%", "22.9%", "20.0%"} <= texts
        plt.close(fig)

    def test_タイトルがある(self, records):
        fig = score_charts.build_pie(score_charts.count_by_department(records))
        assert fig.axes[0].get_title() != ""
        plt.close(fig)


class Test棒グラフ:
    """要件: X軸に所属、Y軸にスコア、タイトル・軸ラベル・凡例。"""

    def test_X軸の目盛りは所属(self, records):
        fig = score_charts.build_bar(score_charts.stats_by_department(records))
        labels = [t.get_text() for t in fig.axes[0].get_xticklabels()]
        assert labels == ["営業", "開発", "管理", "人事"]
        plt.close(fig)

    def test_タイトルと軸ラベルがある(self, records):
        fig = score_charts.build_bar(score_charts.stats_by_department(records))
        ax = fig.axes[0]
        assert ax.get_title() != ""
        assert ax.get_xlabel() != ""
        assert ax.get_ylabel() != ""
        plt.close(fig)

    def test_凡例に平均_最高_最低が並ぶ(self, records):
        fig = score_charts.build_bar(score_charts.stats_by_department(records))
        legend = fig.axes[0].get_legend()
        assert legend is not None
        assert [t.get_text() for t in legend.get_texts()] == ["平均", "最高", "最低"]
        plt.close(fig)

    def test_棒の高さが集計値と一致する(self, records):
        """平均の系列の高さが stats の平均と一致するか。"""
        stats = score_charts.stats_by_department(records)
        fig = score_charts.build_bar(stats)
        heights = [p.get_height() for p in fig.axes[0].patches][:4]
        assert heights == pytest.approx([stats[k].average for k in EXPECTED_COUNTS])
        plt.close(fig)


class Testヒストグラム:
    """要件: 全参加者のスコア分布、適切なビン数。"""

    def test_度数の合計が人数と一致する(self, records):
        scores = [r.score for r in records]
        fig = score_charts.build_histogram(scores)
        assert sum(p.get_height() for p in fig.axes[0].patches) == len(scores) == 35
        plt.close(fig)

    def test_タイトルと軸ラベルがある(self, records):
        fig = score_charts.build_histogram([r.score for r in records])
        ax = fig.axes[0]
        assert ax.get_title() != ""
        assert ax.get_xlabel() != ""
        assert ax.get_ylabel() != ""
        plt.close(fig)


class Test保存:
    def test_3枚できる(self, tmp_path, records):
        paths = score_charts.save_charts(records, tmp_path)
        assert set(paths) == {"pie", "bar", "histogram"}
        for path in paths.values():
            assert path.exists()

    def test_PNGとして書かれている(self, tmp_path, records):
        """拡張子ではなく先頭のシグネチャで確かめる。"""
        for path in score_charts.save_charts(records, tmp_path).values():
            assert path.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"

    def test_出力先が無ければ作る(self, tmp_path, records):
        outdir = tmp_path / "できていない" / "深い階層"
        score_charts.save_charts(records, outdir)
        assert outdir.is_dir()


class TestCLI:
    def test_正常時は0で終わる(self, tmp_path, capsys):
        code = score_charts.main([str(score_charts.DEFAULT_CSV), "--outdir", str(tmp_path)])
        assert code == 0
        assert len(list(tmp_path.glob("*.png"))) == 3

    def test_ファイルが無ければ1で終わる(self, tmp_path, capsys):
        code = score_charts.main([str(tmp_path / "無い.csv"), "--outdir", str(tmp_path)])
        assert code == 1
        assert "見つかりません" in capsys.readouterr().err

    def test_使える行が無ければ1で終わる(self, tmp_path, capsys):
        path = write_csv(tmp_path, "佐藤,営業,満点\n")
        code = score_charts.main([str(path), "--outdir", str(tmp_path)])
        assert code == 1
        assert capsys.readouterr().err != ""
