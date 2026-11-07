---
name: moonseed
description: "Draws secure random bytes and unbiased numbers from them — keys, nonces, salts, identifiers — from any entropy source the program supplies, and raises instead of falling back when there is none. Use it for randomness that must not be guessable, or to draw a private key scalar for a group."
---

# moonseed

```moonbit
test {
  let key = @moonseed.bytes(32, @system.source)
  assert_eq(key.length(), 32)
}
```

Add `moonbitstack/moonseed` for the API and `moonbitstack/moonseed/system` for
the platform's entropy. The second package is the only one that touches a
platform: linking it links the platform's call, which on wasm is the WASI
`random_get` import.

```moonbit
import {
  "moonbitstack/moonseed",
  "moonbitstack/moonseed/system",
}
```

## Bytes

`bytes(n, source)` gives exactly `n` bytes. A negative `n` aborts: it is a
mistake in the caller, not something to paper over with an empty buffer.

```moonbit
test "bytes" {
  let source = @moonseed.Replay::new(b"\x01\x02\x03\x04")
  assert_eq(@moonseed.bytes(3, source), b"\x01\x02\x03")
  assert_eq(source.remaining(), 1)
}
```

## A number in a range

`below(bound, source)` returns a value in [0, `bound`), as wide as `bound`: pass
`b"\x03\xe8"` and you get two bytes holding a number below 1000, not an `Int`.
It rejects instead of taking a modulo, so every value is equally likely.

```moonbit
test "below" {
  let source = @moonseed.Replay::new(b"\x17\x90")
  assert_eq(@moonseed.below(b"\x03\xe8", source), b"\x03\x90")
  assert_eq(source.remaining(), 0)
}
```

`scalar(order, source)` returns a value in [1, `order` - 1], as wide as `order`:
the private key or nonce of a group. Pass the whole order, leading zeros
included.

```moonbit
test "scalar" {
  let order = b"\xff\xff\xff\xff\x00\x00\x00\x00\xff\xff\xff\xff\xff\xff\xff\xff\xbc\xe6\xfa\xad\xa7\x17\x9e\x84\xf3\xb9\xca\xc2\xfc\x63\x25\x51"
  let source = @moonseed.Replay::new(b"\xe4\xb8\x51\x7f\x20\xec\x48\x11\xf7\xd9\xe0\xcf\xa2\xec\x7e\x28\x19\x8a\x34\x1d\xec\xe5\xf7\x7a\x8d\x98\x88\x59\xb9\x44\x62\x41")
  assert_eq(
    @moonseed.scalar(order, source),
    b"\xe4\xb8\x51\x7f\x20\xec\x48\x11\xf7\xd9\xe0\xcf\xa2\xec\x7e\x28\x19\x8a\x34\x1d\xec\xe5\xf7\x7a\x8d\x98\x88\x59\xb9\x44\x62\x41",
  )
}
```

## Your own source

Implement `Source` for a device, a service, a fixture: fill the buffer, or
raise. Anything that keeps the contract plugs in without a change here.

```moonbit
priv struct Device {}

impl @moonseed.Source for Device with fn fill(_self, _buf) {
  raise Failed("the device is unplugged")
}

test "a source of my own" {
  let refused = try {
    ignore(@moonseed.bytes(4, Device::{ }))
    ""
  } catch {
    e => e.to_string()
  }
  assert_eq(refused, "the device is unplugged")
}
```

## Rules that catch people out

- **No seeded fallback.** No bytes means `Unavailable`: `Platform` from the
  platform source, `Exhausted` from a replay, `Failed(reason)` from your own.
  Catch it and decide; never substitute a clock or a counter.
- **`Replay` refuses rather than half-fills.** When fewer bytes are left than a
  fill wants, it raises `Exhausted` and leaves the buffer untouched. Ask
  `remaining()` first if you need to know.
- **`below` and `scalar` keep the width.** The result is as wide as the bound or
  order, so a P-521 scalar is 66 bytes with its top bits clear. Compare them as
  byte strings; do not squeeze them into an `Int`.
- **Caller mistakes abort.** A negative length, a zero bound, an order below 2:
  each aborts. They are bugs, not conditions to recover from.
- **Nothing is cached or wiped.** `@system.source` asks the platform on every
  fill. The buffer is yours to wipe afterwards; this library keeps no copy.
