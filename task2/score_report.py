"""CSV のスコアデータを集計して表示する。

課題: 4-2-2 課題2
- CSV ファイルからデータを読み込み、各参加者のスコアの平均・最高点・最低点を算出する
- 結果を分かりやすく表示する

追加機能:
- 科目ごとの集計と全体サマリー
- 壊れた行（空行・欠損・非数値）を飛ばしたうえで、何行をなぜ飛ばしたか報告する
- 全角混じりでも崩れない桁揃え
"""

from __future__ import annotations

import argparse
import csv
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, NamedTuple, Sequence

DEFAULT_CSV = Path(__file__).parent / "data" / "課題2.csv"

COLUMN_NAME = "名前"
COLUMN_DATE = "日付"
COLUMN_SUBJECT = "科目"
COLUMN_SCORE = "スコア"
REQUIRED_COLUMNS = (COLUMN_NAME, COLUMN_DATE, COLUMN_SUBJECT, COLUMN_SCORE)


class Record(NamedTuple):
    """集計に使える形まで検証を通した1行。"""

    name: str
    date: str
    subject: str
    score: int


class SkippedRow(NamedTuple):
    """集計に使えなかった1行と、その理由。"""

    line: int
    reason: str


@dataclass(frozen=True)
class Stats:
    """あるまとまりのスコアの集計値。

    平均を都度計算せず合計と件数で持つのは、行を1つ足すときに
    それまでの平均から新しい平均を復元する必要をなくすため。
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


def display_width(text: str) -> int:
    """端末での表示幅を返す。全角は2、半角は1。

    str.ljust は「文字数」で詰めるため、日本語が混じった列は必ずずれる。
    「山田太郎」は4文字だが画面では8桁を占めるので、文字数で揃えると
    半角だけの行と4桁ぶんずれて表が読めなくなる。
    """
    return sum(2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1 for ch in text)


def pad(text: str, width: int, *, align_right: bool = False) -> str:
    """表示幅を基準に text を width 桁へ詰める。"""
    space = " " * max(0, width - display_width(text))
    return space + text if align_right else text + space


def render_table(headers: Sequence[str], rows: Sequence[Sequence[str]]) -> str:
    """1列目を左寄せ、それ以外を右寄せにした表を組む。

    見出しと中身の両方から列幅を決める。中身だけで決めると、
    値が短い列で見出しがはみ出して桁が崩れる。
    """
    widths = [
        max(display_width(header), *(display_width(row[i]) for row in rows))
        if rows
        else display_width(header)
        for i, header in enumerate(headers)
    ]
    lines = [
        "  ".join(pad(h, w, align_right=i > 0) for i, (h, w) in enumerate(zip(headers, widths))),
        "  ".join("-" * w for w in widths),
    ]
    lines.extend(
        "  ".join(pad(v, w, align_right=i > 0) for i, (v, w) in enumerate(zip(row, widths)))
        for row in rows
    )
    return "\n".join(lines)


def load_records(path: Path) -> tuple[list[Record], list[SkippedRow]]:
    """CSV を読み、使える行と飛ばした行に分けて返す。

    encoding が utf-8-sig なのは、Excel が保存した CSV には BOM が付くため。
    utf-8 で開くと最初の列名が "﻿名前" になり、列が見つからないという
    実際の原因とかけ離れたエラーになる。BOM が無いファイルでも問題なく読める。
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

    飛ばした行を黙って捨てると「40件のはずが38件」に気づけない。
    理由を持ち回して最後にまとめて報告する。

    ここに来ない行が1種類だけある。何も書かれていない完全な空行は
    csv.DictReader が自分で読み飛ばすため、この関数は呼ばれない。
    報告に出るのは ",,," のように区切りだけがある行のほう。
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
            date=values[COLUMN_DATE],
            subject=values[COLUMN_SUBJECT],
            score=score,
        ),
        "",
    )


def summarize(records: Iterable[Record], key: Callable[[Record], str]) -> dict[str, Stats]:
    """key で分類して集計する。dict の挿入順＝CSV での初出順になる。"""
    result: dict[str, Stats] = {}
    for record in records:
        group = key(record)
        current = result.get(group)
        result[group] = Stats.of(record.score) if current is None else current.merged_with(record.score)
    return result


def stats_table(title: str, label: str, stats: dict[str, Stats]) -> str:
    rows = [
        [name, str(s.count), f"{s.average:.1f}", str(s.highest), str(s.lowest)]
        for name, s in stats.items()
    ]
    headers = [label, "件数", "平均", "最高", "最低"]
    return f"=== {title} ===\n{render_table(headers, rows)}"


def overall_summary(records: Sequence[Record]) -> str:
    best = max(records, key=lambda r: r.score)
    worst = min(records, key=lambda r: r.score)
    total = sum(r.score for r in records)
    participants = len({r.name for r in records})
    return (
        "=== 全体 ===\n"
        f"参加者 {participants} 人 / {len(records)} 件\n"
        f"平均 {total / len(records):.1f}\n"
        f"最高 {best.score}（{best.name}・{best.subject}・{best.date}）\n"
        f"最低 {worst.score}（{worst.name}・{worst.subject}・{worst.date}）"
    )


def build_report(records: Sequence[Record], skipped: Sequence[SkippedRow]) -> str:
    sections = [
        stats_table("参加者ごとの成績", "名前", summarize(records, lambda r: r.name)),
        stats_table("科目ごとの成績", "科目", summarize(records, lambda r: r.subject)),
        overall_summary(records),
    ]
    if skipped:
        lines = "\n".join(f"  {row.line} 行目: {row.reason}" for row in skipped)
        sections.append(f"=== 読み飛ばした行（{len(skipped)} 件）===\n{lines}")
    return "\n\n".join(sections)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="CSV のスコアを参加者ごと・科目ごとに集計する。")
    parser.add_argument(
        "csv_path",
        nargs="?",
        type=Path,
        default=DEFAULT_CSV,
        help=f"集計する CSV（省略時: {DEFAULT_CSV.name}）",
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
        print(f"エラー: 集計できる行が1件もありません（読み飛ばし {len(skipped)} 件）", file=sys.stderr)
        return 1

    print(build_report(records, skipped))
    return 0


if __name__ == "__main__":
    sys.exit(main())
