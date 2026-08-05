"""数当てゲーム。コンピューターが選んだ数をユーザーが当てる。

課題: 4-2-2 課題1
- 1〜100 の乱数を当てる
- 入力に応じて「もっと大きい」「もっと小さい」を表示する
- 正解したら試行回数を知らせる

追加機能: 回数制限モード（決められた回数以内に当てる）
"""

import math
import random

MIN_NUMBER = 1
MAX_NUMBER = 100


def max_attempts_for(lowest: int, highest: int) -> int:
    """その範囲を当てるのに必要な最大手数を返す。

    大小のヒントが返るので、真ん中を選び続ければ候補は毎回半分になる。
    必要な手数は範囲の広さで決まる（1〜100 なら log2(100) ≈ 6.64 で 7 手）。

    定数 7 を直接書くと MIN/MAX を変えたときに破綻する——範囲を 1〜200 にした
    時点で 8 手必要になり、7 手制限では絶対に勝てないゲームになる。
    """
    return math.ceil(math.log2(highest - lowest + 1))


MAX_ATTEMPTS = max_attempts_for(MIN_NUMBER, MAX_NUMBER)


def read_guess() -> int:
    """予想の数値を1つ読み取る。数値でない入力と範囲外は聞き直す。

    入力の検証をここに閉じ込めるのは、ゲーム進行のループから
    「入力が正しいか」の分岐を追い出して読みやすくするため。
    """
    while True:
        raw = input(f"{MIN_NUMBER}〜{MAX_NUMBER} の数字を入力してください: ")
        try:
            value = int(raw)
        except ValueError:
            print("数字で入力してください。")
            continue
        if not MIN_NUMBER <= value <= MAX_NUMBER:
            print(f"{MIN_NUMBER} から {MAX_NUMBER} の範囲で入力してください。")
            continue
        return value


def read_yes_no(prompt: str) -> bool:
    """y / n を読み取る。そのまま Enter を押したときは n として扱う。"""
    while True:
        raw = input(prompt).strip().lower()
        if raw in ("y", "yes"):
            return True
        if raw in ("", "n", "no"):
            return False
        print("y か n で入力してください。")


def play(limit: int | None = None) -> None:
    """1ゲーム分を進める。limit を渡すとその回数までしか挑戦できない。

    limit を「無制限 = None」で表すのは、0 や -1 のような番兵を使うと
    呼び出し側で意味を覚える必要が出るため。
    """
    answer = random.randint(MIN_NUMBER, MAX_NUMBER)
    attempts = 0

    while limit is None or attempts < limit:
        if limit is not None:
            print(f"残り {limit - attempts} 回")

        guess = read_guess()
        attempts += 1

        if guess < answer:
            print("もっと大きい")
        elif guess > answer:
            print("もっと小さい")
        else:
            print(f"正解！ {attempts} 回で当たりました。")
            return

    print(f"残念、{limit} 回では当てられませんでした。答えは {answer} でした。")


def main() -> None:
    print(f"数当てゲーム（{MIN_NUMBER}〜{MAX_NUMBER}）")
    limited = read_yes_no(f"回数制限モードで遊ぶ？（{MAX_ATTEMPTS} 回以内に当てる）[y/N]: ")
    play(MAX_ATTEMPTS if limited else None)


if __name__ == "__main__":
    try:
        main()
    except (EOFError, KeyboardInterrupt):
        # Ctrl+C / Ctrl+Z は「やめる」という正常な操作なので、
        # 赤いトレースバックではなく普通のメッセージで終わらせる
        print("\n中断しました。")
