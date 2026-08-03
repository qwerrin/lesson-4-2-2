"""回数制限を 7 回にした根拠を確かめる。

guess_game.py の MAX_ATTEMPTS = 7 は log2(100) ≈ 6.64 の切り上げで決めたが、
式だけでは「本当に足りるのか」が実感できなかったため、1〜100 のすべての答えについて
まん中を選び続けたときの手数を数え上げた。
"""

from collections import Counter

MIN_NUMBER = 1
MAX_NUMBER = 100


def steps(answer: int, lo: int = MIN_NUMBER, hi: int = MAX_NUMBER) -> int:
    """まん中を選び続けたとき、answer に到達するまでの手数を返す。"""
    count = 0
    while lo <= hi:
        mid = (lo + hi) // 2
        count += 1
        if mid == answer:
            return count
        if mid < answer:
            lo = mid + 1
        else:
            hi = mid - 1
    raise AssertionError("範囲内の答えなら必ず到達する")


def main() -> None:
    results = [steps(a) for a in range(MIN_NUMBER, MAX_NUMBER + 1)]
    average = sum(results) / len(results)

    print(f"最小 {min(results)} 手 / 最大 {max(results)} 手 / 平均 {average:.2f} 手")
    print("手数の分布:")
    for count, times in sorted(Counter(results).items()):
        print(f"  {count} 手: {times:3d} 通り  {'#' * times}")


if __name__ == "__main__":
    main()
