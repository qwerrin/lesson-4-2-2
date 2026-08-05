"""guess_game のテスト。

input() と print() に依存しているため、monkeypatch で入力を差し替え、
出力は capsys で受け取る。乱数も固定して結果を決め打ちにする。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import guess_game  # noqa: E402


@pytest.fixture
def answer_is(monkeypatch):
    """正解の数を固定する。乱数のままだとテストの結果が毎回変わるため。"""

    def _set(value: int):
        monkeypatch.setattr(guess_game.random, "randint", lambda _lo, _hi: value)

    return _set


@pytest.fixture
def types(monkeypatch):
    """ユーザーが順番に打ち込む文字列を差し替える。"""

    def _set(*values: str):
        it = iter(values)
        monkeypatch.setattr("builtins.input", lambda _prompt="": next(it))

    return _set


class TestMaxAttempts:
    """回数制限の上限は範囲から計算する。定数で持つと範囲変更で破綻するため。"""

    def test_1から100なら7回(self):
        assert guess_game.MAX_ATTEMPTS == 7

    @pytest.mark.parametrize(
        ("upper", "expected"),
        [(50, 6), (100, 7), (200, 8), (1000, 10)],
    )
    def test_範囲に連動する(self, upper: int, expected: int):
        assert guess_game.max_attempts_for(1, upper) == expected

    def test_上限は計算結果から取っている(self):
        # ここが無いと「MAX_ATTEMPTS を定数 7 に戻す」変更を検出できない。
        # 範囲だけ広げて上限を据え置くと、絶対に勝てないゲームになる
        assert guess_game.MAX_ATTEMPTS == guess_game.max_attempts_for(
            guess_game.MIN_NUMBER, guess_game.MAX_NUMBER
        )


class TestReadGuess:
    def test_数値をそのまま返す(self, types):
        types("42")
        assert guess_game.read_guess() == 42

    def test_数字でなければ聞き直す(self, types, capsys):
        types("abc", "50")
        assert guess_game.read_guess() == 50
        assert "数字で入力してください。" in capsys.readouterr().out

    def test_小数は数字として扱わない(self, types):
        # int("3.5") は ValueError。整数を当てるゲームなので弾く方を選んだ
        types("3.5", "7")
        assert guess_game.read_guess() == 7

    @pytest.mark.parametrize("out_of_range", ["0", "101", "-5"])
    def test_範囲外は聞き直す(self, types, capsys, out_of_range: str):
        types(out_of_range, "50")
        assert guess_game.read_guess() == 50
        assert "範囲で入力してください。" in capsys.readouterr().out

    @pytest.mark.parametrize("boundary", [1, 100])
    def test_範囲の境界は通す(self, types, boundary: int):
        types(str(boundary))
        assert guess_game.read_guess() == boundary


class TestReadYesNo:
    @pytest.mark.parametrize("yes", ["y", "Y", "yes", "YES"])
    def test_yesとみなす入力(self, types, yes: str):
        types(yes)
        assert guess_game.read_yes_no("? ") is True

    @pytest.mark.parametrize("no", ["n", "N", "no", ""])
    def test_noとみなす入力(self, types, no: str):
        # 空入力を no にしているのは、プロンプトの [y/N] 表記と揃えるため
        types(no)
        assert guess_game.read_yes_no("? ") is False

    def test_それ以外は聞き直す(self, types, capsys):
        types("maybe", "y")
        assert guess_game.read_yes_no("? ") is True
        assert "y か n で入力してください。" in capsys.readouterr().out


class TestPlay:
    def test_一発で当てたら1回と表示する(self, answer_is, types, capsys):
        answer_is(42)
        types("42")
        guess_game.play()
        assert "正解！ 1 回で当たりました。" in capsys.readouterr().out

    def test_小さすぎればもっと大きいと出る(self, answer_is, types, capsys):
        answer_is(80)
        types("20", "80")
        guess_game.play()
        assert "もっと大きい" in capsys.readouterr().out

    def test_大きすぎればもっと小さいと出る(self, answer_is, types, capsys):
        answer_is(20)
        types("80", "20")
        guess_game.play()
        assert "もっと小さい" in capsys.readouterr().out

    def test_試行回数は外した回数を含む(self, answer_is, types, capsys):
        answer_is(50)
        types("10", "90", "50")
        guess_game.play()
        assert "正解！ 3 回で当たりました。" in capsys.readouterr().out

    def test_入力し直した回数は試行に数えない(self, answer_is, types, capsys):
        # 検証で弾かれた入力まで数えると、ユーザーは打ち間違いで損をする
        answer_is(50)
        types("abc", "999", "50")
        guess_game.play()
        assert "正解！ 1 回で当たりました。" in capsys.readouterr().out


class TestPlayWithLimit:
    def test_残り回数を毎回表示する(self, answer_is, types, capsys):
        answer_is(50)
        types("50")
        guess_game.play(limit=3)
        assert "残り 3 回" in capsys.readouterr().out

    def test_使い切ったら答えを明かして終わる(self, answer_is, types, capsys):
        answer_is(99)
        types("1", "2", "3")
        guess_game.play(limit=3)
        out = capsys.readouterr().out
        assert "残念、3 回では当てられませんでした。" in out
        assert "答えは 99 でした。" in out

    def test_上限内に当てれば負け判定にならない(self, answer_is, types, capsys):
        answer_is(50)
        types("10", "50")
        guess_game.play(limit=3)
        out = capsys.readouterr().out
        assert "正解！ 2 回で当たりました。" in out
        assert "残念" not in out

    def test_制限なしなら残り回数を表示しない(self, answer_is, types, capsys):
        answer_is(50)
        types("50")
        guess_game.play()
        assert "残り" not in capsys.readouterr().out
