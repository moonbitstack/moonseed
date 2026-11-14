# Guide

> From an empty package to a key, a range and a scalar. Seven steps, each with the code that
> runs and the value it produces.

## 01 Install | Two packages: the contract, and the platform's entropy.

Add the library. The root package has no platform code at all; `moonseed/system` is the only
part that talks to the host, so a program that brings its own source never links it.

```text
moon add moonbitstack/moonseed
```

Import the two packages by name:

```mbt
import {
  "moonbitstack/moonseed",
  "moonbitstack/moonseed/system",
}
```

That is the whole setup: no initialisation, no global state, nothing to close.

## 02 First bytes | `bytes` fills the buffer from the source you give it.

`bytes(n, source)` asks the source for exactly `n` bytes and hands them back. The source is a
value, not a global: pass the platform's `@system.source` in a program, and a fixed one in a test.

```mbt
test "four bytes from a fixed source" {
  let source = @moonseed.Replay::new(b"\x9f\x2c\x07\xd1")
  assert_eq(@moonseed.bytes(4, source), b"\x9f\x2c\x07\xd1")
  assert_eq(source.remaining(), 0)
}
```

```mbt
test "thirty-two bytes from the platform" {
  let key = @moonseed.bytes(32, @system.source)
  assert_eq(key.length(), 32)
}
```

!! On a host without WASI there is no platform source, and the second draw raises
`Unavailable::Platform` rather than making bytes up. Run it where a platform exists.

A negative length aborts: it is a mistake in the caller, and an empty buffer would hide it.

## 03 A number in a range | `below` rejects; it does not take a remainder.

`below(bound, source)` reads `bound` as a big-endian number and returns one in [0, `bound`), as
wide as `bound`. It draws as many bytes as `bound - 1` needs, clears the unused high bits of the
first, and draws again while the value is at or above `bound` — so every value is equally likely.

```mbt
test "what it prints" {
  let source = @moonseed.Replay::new(b"\x17\x90")
  println(@moonseed.below(b"\x03\xe8", source))
}
```

```text
b"\x03\x90"
```

```mbt
test "a draw at or above the bound is thrown away" {
  // 1000 needs ten bits, so 0xffff is cut to 0x03ff: 1023, still too big.
  let source = @moonseed.Replay::new(b"\xff\xff\x03\xe7")
  assert_eq(@moonseed.below(b"\x03\xe8", source), b"\x03\xe7")
  assert_eq(source.remaining(), 0)
}
```

Two edges worth knowing: a bound of `b"\x01"` has one value below it and reads nothing, and a
zero bound aborts. The answer keeps the bound's width, leading zero bytes included, so it is a
number you can compare as bytes rather than an `Int`.

## 04 A scalar | A private key, drawn the way FIPS 186-5 draws one.

`scalar(order, source)` returns a value in [1, `order` - 1], as wide as `order`. It keeps the
leftmost bits of a draw as long as the order and draws again on zero or on a value at or above
the order.

```mbt
test "a P-256 key from a fixed stream" {
  let order = b"\xff\xff\xff\xff\x00\x00\x00\x00\xff\xff\xff\xff\xff\xff\xff\xff\xbc\xe6\xfa\xad\xa7\x17\x9e\x84\xf3\xb9\xca\xc2\xfc\x63\x25\x51"
  let source = @moonseed.Replay::new(b"\xe4\xb8\x51\x7f\x20\xec\x48\x11\xf7\xd9\xe0\xcf\xa2\xec\x7e\x28\x19\x8a\x34\x1d\xec\xe5\xf7\x7a\x8d\x98\x88\x59\xb9\x44\x62\x41")
  assert_eq(@moonseed.scalar(order, source), b"\xe4\xb8\x51\x7f\x20\xec\x48\x11\xf7\xd9\xe0\xcf\xa2\xec\x7e\x28\x19\x8a\x34\x1d\xec\xe5\xf7\x7a\x8d\x98\x88\x59\xb9\x44\x62\x41")
  assert_eq(source.remaining(), 0)
}
```

A P-521 order needs 521 bits in 66 bytes, so seven bits of every draw are spare. They are
shifted out of the whole number, not masked off the first byte: a byte below becomes a value
in the low place.

```mbt
test "a P-521 scalar is as wide as its order" {
  let order = b"\x01\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xfa\x51\x86\x87\x83\xbf\x2f\x96\x6b\x7f\xcc\x01\x48\xf7\x09\xa5\xd0\x3b\xb5\xc9\xb8\x89\x9c\x47\xae\xbb\x6f\xb7\x1e\x91\x38\x64\x09"
  let buf = FixedArray::make(66, b'\x00')
  buf[65] = b'\x80'
  let d = @moonseed.scalar(order, @moonseed.Replay::new(Bytes::from_array(buf)))
  assert_eq(d.length(), 66)
  assert_eq(d[65], b'\x01')
  println(d)
}
```

```text
b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x01"
```

An order below 2 aborts. So does a bound of zero: both are caller mistakes, not conditions to
recover from.

## 05 A source of your own | One method: fill the buffer, or raise.

Anything that implements `Source` plugs in without a change here: a hardware device, a service,
a fixture. Fill the buffer completely, or raise — a source that fills half of it has broken the
contract, because the caller cannot tell how much is real.

```mbt
priv struct Queue {
  mut data : Bytes
}

impl @moonseed.Source for Queue with fn fill(self, buf) {
  if self.data.length() < buf.length() {
    raise @moonseed.Unavailable::Failed("the queue ran dry")
  }
  for i in 0..<buf.length() {
    buf[i] = self.data[i]
  }
  self.data = self.data[buf.length():].to_owned()
}
```

```mbt
test "my own source, and its refusal" {
  let source : Queue = { data: b"\x11\x22" }
  assert_eq(@moonseed.bytes(2, source), b"\x11\x22")
  let refused = try {
    ignore(@moonseed.bytes(1, source))
    ""
  } catch {
    e => e.to_string()
  }
  assert_eq(refused, "the queue ran dry")
}
```

`@moonseed.Replay` is the same shape, one you do not have to write: it hands out the bytes it
was given, in order, and refuses once they are spent.

## 06 When there are no bytes | Three refusals, three decisions.

The call raises `Unavailable`, and the variant tells you which way it failed: `Platform` means
the host has no source or its source failed, `Exhausted` means a replay is spent, and
`Failed(reason)` carries your own source's reason. Decide at the call site; substituting a
clock, a counter or a hash of them turns a visible failure into a guessable key.

```mbt
test "decide at the call site" {
  let refused = try {
    ignore(@moonseed.bytes(8, @moonseed.Replay::new(b"\x01")))
    "got bytes"
  } catch {
    @moonseed.Unavailable::Exhausted => "the replay ran out"
    @moonseed.Unavailable::Platform => "no platform source"
    @moonseed.Unavailable::Failed(reason) => reason
  }
  assert_eq(refused, "the replay ran out")
}
```

There is no fallback inside the library either: no source means the call raises, it never
quietly reaches for a seeded generator.

## 07 Where it stops | What this library is not.

- **Not a generator.** No seed, no stream, no reproducibility. For a reproducible stream, use a seeded generator and seed it from these bytes.
- **No stretching.** It moves entropy; 32 bytes stay 32 bytes. A key longer than the bytes you drew has less entropy than its length suggests.
- **No retrying.** Whether to retry a refusal, and how often, is your policy — and only you know how long a key can wait.
- **No cache.** `@system.source` asks the platform on every fill and keeps nothing; the buffer is yours to wipe with `buf.fill(b'\x00')`.
- **No promise about timing.** The rejection loop leaves a timing trace. Bound the retries, or sample differently, if that matters to you.
