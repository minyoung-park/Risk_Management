"""샘플 일별 지표 CSV 재생성용 스크립트(일회성 생성)."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    start = date(2024, 6, 1)
    rows: list[dict[str, object]] = []
    for i in range(36):
        d = start + timedelta(days=i)
        if i < 28:
            c = 1 + (i % 5)
            v = 40000 + i * 1800
            cm = 40 + i * 6
            si = 50 + (i % 7)
            nw = 2 + (i % 4)
        elif i < 32:
            c = 25 + (i - 28) * 35
            v = 180000 + (i - 28) * 90000
            cm = 400 + (i - 28) * 220
            si = 90 + (i - 28) * 18
            nw = 18 + (i - 28) * 12
        elif i < 34:
            c = 5200 if i == 32 else 6100
            v = 1_200_000_000 if i == 32 else 1_580_000_000
            cm = 240_000 if i == 32 else 310_000
            si = 420 if i == 32 else 455
            nw = 1100 if i == 32 else 1280
        else:
            c = 35 if i == 34 else 8
            v = 28_000_000 if i == 34 else 9_000_000
            cm = 4200 if i == 34 else 900
            si = 150 if i == 34 else 105
            nw = 120 if i == 34 else 55

        rows.append(
            {
                "date": d.isoformat(),
                "candidate_video_count": c,
                "candidate_video_total_views": v,
                "candidate_video_comment_count": cm,
                "search_index": si,
                "news_count": nw,
                "creator_channel_daily_views": max(52000, 94000 - i * 380),
                "creator_channel_subscriber_change": max(-260, -1 - i * 5),
            }
        )

    df = pd.DataFrame(rows)
    path = ROOT / "data" / "sample_daily_metrics.csv"
    df.to_csv(path, index=False)
    xs = df["candidate_video_count"].to_numpy(dtype=float)
    m, s = float(xs.mean()), float(xs.std(ddof=0))
    zmax = (float(xs.max()) - m) / s if s > 1e-9 else 0.0
    print(path, "zmax(candidate_count)=", round(zmax, 3))


if __name__ == "__main__":
    main()
