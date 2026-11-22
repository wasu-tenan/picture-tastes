# Steaming Ramen — The picture that tastes of one ingredient

[![make.fun](https://make.fun/badge/the-picture-that-tastes-of-one-20261122-2047.svg)](https://make.fun/bounty/the-picture-that-tastes-of-one-20261122-2047)
[![Rank](https://make.fun/badge/the-picture-that-tastes-of-one-20261122-2047/wasu-tenan/picture-tastes/rank.svg)](https://make.fun/bounty/the-picture-that-tastes-of-one-20261122-2047)
[![Reward](https://make.fun/badge/the-picture-that-tastes-of-one-20261122-2047/wasu-tenan/picture-tastes/reward.svg)](https://make.fun/bounty/the-picture-that-tastes-of-one-20261122-2047)

A program that paints one close-up picture of a steaming bowl of ramen —
glistening golden broth, wavy noodles, a jammy soft egg, narutomaki, spring
onion and chopsticks — rendered entirely in code, pixel by pixel, with no
external images.

## Run

```sh
python3 main.py
```

This writes `entry.png` to `/output` by default. Pass `--output <path>` or
set `MAKEFUN_OUTPUT_DIR` to choose another location.

## How it works

`main.py` (Python 3.13, standard library only) paints the scene into an RGB
buffer — warm wood table, lacquered red bowl, golden broth with oil sheen and
chili-oil drops, noodle strands, soft-egg halves with glossy yolks, narutomaki
spirals, spring-onion rings, chopsticks and rising steam — then encodes the
buffer as a PNG by hand with `zlib` (raw scanlines → deflate → PNG chunks
with CRC32). The output is deterministic: every run produces the same bytes.

## Entry

- Competition: [The picture that tastes of one ingredient](https://make.fun/bounty/the-picture-that-tastes-of-one-20261122-2047)
- Output: one 1024×1024 PNG, well under the 1 MiB cap

---

[Try make.fun](https://make.fun/?ref=2mmz0hmg)
