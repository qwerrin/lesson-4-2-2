"""CSV のスコアデータから3種類のグラフを作り、画像として保存する。

課題: 4-2-2 課題3
- 円グラフ     … 所属ごとの参加者数（割合をパーセンテージ付きで表示）
- 棒グラフ     … 所属ごとの平均・最高・最低スコア
- ヒストグラム … 全参加者のスコア分布

集計は課題2と同じ考え方で、平均を持たず「合計と件数」で持つ。
描画に必要なものだけ最後に割る。
"""

from __future__ import annotations

import argparse
import csv
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, NamedTuple, Sequence

import matplotlib

# 画面を持たない環境（テスト・CI）でも動くように、pyplot を読む前に決める。
# 既定のバックエンドはウィンドウを開こうとするため、savefig だけしたい用途では邪魔になる。
matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402

DEFAULT_CSV = Path(__file__).parent / "data" / "課題3.csv"
DEFAULT_OUTPUT_DIR = Path(__file__).parent / "charts"

COLUMN_NAME = "名前"
COLUMN_DEPARTMENT = "所属"
COLUMN_SCORE = "スコア"
REQUIRED_COLUMNS = (COLUMN_NAME, COLUMN_DEPARTMENT, COLUMN_SCORE)

# 日本語を描けるフォントの候補。上から順に、実際に入っているものを使う。
# 1つに決め打ちすると、そのフォントが無い環境で matplotlib が既定フォントに
# 黙って戻り、ラベルがすべて □ になる。例外にはならないので画像だけができあがる。
JAPANESE_FONT_CANDIDATES = (
    "Yu Gothic",
    "Meiryo",
    "MS Gothic",
    "Noto Sans JP",
    "BIZ UDGothic",
    "Hiragino Sans",
    "IPAexGothic",
)

# matplotlib の初期値。日本語フォントを差し込むときの土台にする。
_DEFAULT_SANS_SERIF = tuple(plt.rcParams["font.sans-serif"])

CHART_FILENAMES = {
    "pie": "01-pie.png",
    "bar": "02-bar.png",
    "histogram": "03-histogram.png",
}


class Record(NamedTuple):
    """集計に使える形まで検証を通した1行。"""

    name: str
    department: str
    score: int


class SkippedRow(NamedTuple):
    """集計に使えなかった1行と、その理由。"""

    line: int
    reason: str


@dataclass(frozen=True)
class Stats:
    """あるまとまりのスコアの集計値。

    平均ではなく合計と件数で持つ。割ってしまうと、行を1つ足すときに
    元の合計を復元できない。
    """

    count: int
    total: int
    highest: int
    lowest: int

    @property
    def average(self) -> float:
        return self.total / self.count

    def merged_with(self, score: int) -> Stats:
        """スコアを1つ加えた新しい Stats を返す（自分は書き換えない）。"""
        return Stats(
            count=self.count + 1,
            total=self.total + score,
            highest=max(self.highest, score),
            lowest=min(self.lowest, score),
        )

    @classmethod
    def of(cls, score: int) -> Stats:
        return cls(count=1, total=score, highest=score, lowest=score)


def load_records(path: Path) -> tuple[list[Record], list[SkippedRow]]:
    """CSV を読み、使える行と飛ばした行に分けて返す。

    encoding が utf-8-sig なのは、Excel が保存した CSV には BOM が付くため。
    utf-8 で開くと最初の列名が "﻿名前" になり、実際の原因とかけ離れた
    「列が見つかりません」というエラーになる。
    """
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError(f"{path} が空です。ヘッダー行がありません。")

        missing = [c for c in REQUIRED_COLUMNS if c not in reader.fieldnames]
        if missing:
            raise ValueError(
                f"{path} に必要な列がありません: {'、'.join(missing)}"
                f"（見つかった列: {'、'.join(reader.fieldnames)}）"
            )

        records: list[Record] = []
        skipped: list[SkippedRow] = []
        for row in reader:
            record, reason = _parse_row(row)
            if record is None:
                skipped.append(SkippedRow(line=reader.line_num, reason=reason))
            else:
                records.append(record)

    return records, skipped


def _parse_row(row: dict[str, str | None]) -> tuple[Record | None, str]:
    """1行を Record にする。できないときは理由を返す。

    飛ばした行を黙って捨てると「35 件のはずが 33 件」に気づけない。
    グラフは件数が減っても、それらしい形で描けてしまう。
    """
    values = {key: (row.get(key) or "").strip() for key in REQUIRED_COLUMNS}

    if not any(values.values()):
        return None, "空行"

    empty = [key for key, value in values.items() if not value]
    if empty:
        return None, f"{'、'.join(empty)} が空"

    try:
        score = int(values[COLUMN_SCORE])
    except ValueError:
        return None, f"スコアが数値ではない: {values[COLUMN_SCORE]!r}"

    return (
        Record(
            name=values[COLUMN_NAME],
            department=values[COLUMN_DEPARTMENT],
            score=score,
        ),
        "",
    )


def count_by_department(records: Iterable[Record]) -> dict[str, int]:
    """所属ごとの人数。dict の挿入順＝CSV での初出順になる。"""
    counts: dict[str, int] = {}
    for record in records:
        counts[record.department] = counts.get(record.department, 0) + 1
    return counts


def stats_by_department(records: Iterable[Record]) -> dict[str, Stats]:
    """所属ごとの集計値。"""
    result: dict[str, Stats] = {}
    for record in records:
        current = result.get(record.department)
        result[record.department] = (
            Stats.of(record.score) if current is None else current.merged_with(record.score)
        )
    return result


def bin_count(values: Sequence[int]) -> int:
    """ヒストグラムのビン数をスタージェスの公式で返す。

    k = ceil(log2(n)) + 1

    定数で書くとデータ件数が変わったときに合わなくなる。35 件に合わせて 7 と
    書いてしまうと、10 件のデータでも 100 件のデータでも 7 本のままになり、
    「適切なビン数」という要件が壊れていることに気づけない。
    課題1の回数制限を範囲から計算したのと同じ理由で、件数から出す。
    """
    if not values:
        raise ValueError("ビン数を決められません: 値が1つもありません")
    return math.ceil(math.log2(len(values))) + 1


def use_japanese_font() -> str:
    """日本語を描けるフォントを選んで matplotlib に設定し、その名前を返す。

    matplotlib の既定フォント DejaVu Sans は日本語のグリフを持たない。
    そのまま描いてもエラーにはならず、警告を出して □ を並べた画像ができる。
    戻り値も例外も正常に見えるので、画像を開くまで気づけない。
    """
    installed = {f.name for f in font_manager.fontManager.ttflist}
    for candidate in JAPANESE_FONT_CANDIDATES:
        if candidate in installed:
            plt.rcParams["font.family"] = "sans-serif"
            # 現在の値に足すのではなく、既定値から組み直す。
            # 図を作るたびにこの関数を呼ぶので、足していくとリストが伸び続ける。
            # 先頭は常に candidate なので、テストからは伸びていることが見えない。
            plt.rcParams["font.sans-serif"] = [candidate, *_DEFAULT_SANS_SERIF]
            # 日本語フォントには U+2212（マイナス記号）を持たないものがあり、
            # 負の目盛りが □ になる。ASCII のハイフンで描かせて避ける。
            plt.rcParams["axes.unicode_minus"] = False
            return candidate

    raise RuntimeError(
        "日本語を表示できるフォントが見つかりません。"
        f"次のいずれかを入れてください: {'、'.join(JAPANESE_FONT_CANDIDATES)}"
    )


def build_pie(counts: dict[str, int]) -> Figure:
    """所属ごとの人数の内訳を円グラフにする。"""
    use_japanese_font()
    fig, ax = plt.subplots(figsize=(7, 6))
    total = sum(counts.values())
    ax.pie(
        list(counts.values()),
        labels=list(counts),
        autopct="%1.1f%%",
        startangle=90,
        counterclock=False,
        wedgeprops={"edgecolor": "white", "linewidth": 1.5},
    )
    # 既定では楕円に潰れる。円グラフは面積で割合を読むので正円にする。
    ax.set_aspect("equal")
    ax.set_title(f"所属ごとの参加者数（全 {total} 人）")
    fig.tight_layout()
    return fig


def build_bar(stats: dict[str, Stats]) -> Figure:
    """所属ごとの平均・最高・最低スコアを棒グラフにする。

    3系列を並べるのは、凡例に意味を持たせるため。1系列だけの棒グラフに
    凡例を付けても、色と系列名が1対1で並ぶだけで何も伝わらない。
    """
    use_japanese_font()
    departments = list(stats)
    series = {
        "平均": [stats[d].average for d in departments],
        "最高": [float(stats[d].highest) for d in departments],
        "最低": [float(stats[d].lowest) for d in departments],
    }

    fig, ax = plt.subplots(figsize=(9, 6))
    positions = range(len(departments))
    width = 0.26
    for i, (label, values) in enumerate(series.items()):
        offset = (i - 1) * width
        bars = ax.bar([p + offset for p in positions], values, width, label=label)
        ax.bar_label(bars, fmt="%.1f", fontsize=8, padding=2)

    ax.set_xticks(list(positions))
    ax.set_xticklabels(departments)
    ax.set_title("所属ごとのスコア（平均・最高・最低）")
    ax.set_xlabel("所属")
    ax.set_ylabel("スコア")
    # 下限は 0 のままにする。70〜95 に絞れば差は大きく見えるが、
    # 棒グラフは「棒の長さの比」で読まれるので、途中から描くと差を誇張して伝える。
    # 上限だけ 105 にしているのは、bar_label の数字が枠に当たらないようにするため。
    ax.set_ylim(0, 105)
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    ax.set_axisbelow(True)
    fig.tight_layout()
    return fig


def build_histogram(scores: Sequence[int]) -> Figure:
    """全参加者のスコア分布をヒストグラムにする。"""
    use_japanese_font()
    bins = bin_count(scores)
    fig, ax = plt.subplots(figsize=(9, 6))
    ax.hist(scores, bins=bins, edgecolor="white", linewidth=1.2)
    ax.set_title(f"スコアの分布（{len(scores)} 人 / {bins} 区間）")
    ax.set_xlabel("スコア")
    ax.set_ylabel("人数")
    ax.grid(axis="y", alpha=0.3)
    ax.set_axisbelow(True)
    fig.tight_layout()
    return fig


def save_charts(records: Sequence[Record], outdir: Path) -> dict[str, Path]:
    """3枚のグラフを outdir に保存し、種類ごとのパスを返す。"""
    outdir.mkdir(parents=True, exist_ok=True)

    figures = {
        "pie": build_pie(count_by_department(records)),
        "bar": build_bar(stats_by_department(records)),
        "histogram": build_histogram([r.score for r in records]),
    }

    saved: dict[str, Path] = {}
    for kind, fig in figures.items():
        path = outdir / CHART_FILENAMES[kind]
        fig.savefig(path, dpi=150)
        plt.close(fig)
        saved[kind] = path
    return saved


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="CSV のスコアから円グラフ・棒グラフ・ヒストグラムを作って保存する。"
    )
    parser.add_argument(
        "csv_path",
        nargs="?",
        type=Path,
        default=DEFAULT_CSV,
        help=f"読み込む CSV（省略時: {DEFAULT_CSV.name}）",
    )
    parser.add_argument(
        "--outdir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"画像の保存先（省略時: {DEFAULT_OUTPUT_DIR.name}/）",
    )
    args = parser.parse_args(argv)

    try:
        records, skipped = load_records(args.csv_path)
    except FileNotFoundError:
        print(f"エラー: ファイルが見つかりません: {args.csv_path}", file=sys.stderr)
        return 1
    except (ValueError, UnicodeDecodeError) as e:
        print(f"エラー: {e}", file=sys.stderr)
        return 1

    if not records:
        print(
            f"エラー: 集計できる行が1件もありません（読み飛ばし {len(skipped)} 件）",
            file=sys.stderr,
        )
        return 1

    try:
        saved = save_charts(records, args.outdir)
    except RuntimeError as e:
        print(f"エラー: {e}", file=sys.stderr)
        return 1

    counts = count_by_department(records)
    print(f"{len(records)} 件を読み込みました（所属 {len(counts)} 種）")
    for path in saved.values():
        print(f"  保存: {path}")

    if skipped:
        print(f"\n=== 読み飛ばした行（{len(skipped)} 件）===")
        for row in skipped:
            print(f"  {row.line} 行目: {row.reason}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
