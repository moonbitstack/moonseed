<div align="center">

<h1>moonseed</h1>

<p><b>Secure random bytes, and numbers drawn from them without bias, over any entropy source the caller supplies.</b></p>

<p>
<a href="https://moonbitstack.github.io/moonseed/">Home</a> ·
<a href="https://moonbitstack.github.io/moonseed/guide.html">Guide</a> ·
<a href="https://moonbitstack.github.io/moonseed/api.html">API</a> ·
<a href="https://moonbitstack.github.io/moonseed/sampling.html">Bench</a> ·
<a href="https://mooncakes.io/docs/moonbitstack/moonseed">mooncakes</a>
</p>

</div>

Three lines, and the platform fills the buffer:

```moonbit
test "draw" {
  let key = @moonseed.bytes(32, @system.source) // 32 uniform bytes
  let n = @moonseed.below(b"\x03\xe8", @system.source) // in [0, 1000)
  let d = @moonseed.scalar(b"\x05", @system.source) // in [1, 4)
  ignore((key, n, d))
}
```

`moon run src/examples/tour` walks the whole API once, so you can watch it ask
for bytes. The guide goes from an empty package to a key, a range and a scalar;
the reference lists every item with the example beside it.

## Packages

| Package | What it holds | Depends on |
|:--:|:--|:--|
| `moonseed` | `Source`, `Unavailable`, `bytes`, `below`, `scalar`, `Replay` | nothing |
| `moonseed/system` | `source`, the platform's entropy | core `env` |

The root package touches no platform. Linking `system` links the platform's call,
which on wasm is the WASI `random_get` import; a program for a wasm host without
WASI uses the root package with a source of its own.

## Sources

| Source | Where the bytes come from |
|:--:|:--|
| `@system.source` | `crypto.getRandomValues` on JavaScript, WASI `random_get` on wasm and wasm-gc, the runtime on native |
| `Replay::new(bytes)` | the bytes given, in order; exhausted after |
| your own | anything that implements `Source` |

A source is one method: fill the buffer, or raise. Nothing else is
required of it, so a device, a service and a file reach the library the same
way.

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

No source falls back to a seeded generator. When there are no bytes to be had,
the call raises `Unavailable`: `Platform` from the platform source, `Exhausted`
from a replay, `Failed(reason)` from a source of your own. A key drawn from a
fallback looks like any other key and is guessable, so the failure is the
caller's to see.

```moonbit
test "the three refusals" {
  assert_eq(
    @moonseed.Unavailable::Platform.to_string(),
    "the platform has no entropy source",
  )
  assert_eq(
    @moonseed.Unavailable::Exhausted.to_string(),
    "the replay source is exhausted",
  )
  assert_eq(
    @moonseed.Unavailable::Failed("the device is unplugged").to_string(),
    "the device is unplugged",
  )
}
```

## Replaying bytes

`Replay` hands out the bytes it was built from, in order, and then raises
`Exhausted`. It is built from bytes alone, so a draw can be pinned to a fixed
sequence without a platform in sight.

```moonbit
test "replay" {
  let source = @moonseed.Replay::new(b"\x07\xff\x02")
  assert_eq(@moonseed.below(b"\x0a", source), b"\x07")
  // 0xff keeps its low four bits, which is 15: at or above the bound, so the
  // next byte is drawn instead.
  assert_eq(@moonseed.below(b"\x0a", source), b"\x02")
  assert_eq(source.remaining(), 0)
}
```

A fill wants more bytes than are left: nothing is copied, the buffer is left as
it was, and the call raises `Exhausted`. `remaining()` says how many bytes there
are to give.

```moonbit
test "a short replay gives nothing" {
  let source = @moonseed.Replay::new(b"\x01\x02\x03")
  let buf = FixedArray::make(4, b'\x00')
  let refused = try {
    source.fill(buf)
    false
  } catch {
    @moonseed.Unavailable::Exhausted => true
    _ => false
  }
  assert_true(refused)
  assert_eq(buf, [b'\x00', b'\x00', b'\x00', b'\x00'])
  assert_eq(source.remaining(), 3)
}
```

## Sampling

`below(bound, source)` reads `bound` as a big-endian number and returns one in
[0, `bound`), as wide as `bound`. It draws as many bytes as `bound - 1` needs,
clears the unused high bits of the first, and draws again while the value is at
or above `bound`. Every value is equally likely; reducing a wider draw modulo
`bound` would favour the small ones.

```moonbit
test "below 1000" {
  let source = @moonseed.Replay::new(b"\x17\x90\x37\xdd")
  assert_eq(@moonseed.below(b"\x03\xe8", source), b"\x03\x90")
  assert_eq(@moonseed.below(b"\x03\xe8", source), b"\x03\xdd")
  assert_eq(source.remaining(), 0)
}
```

`scalar(order, source)` returns a value in [1, `order` - 1], as wide as `order`:
a private key or a nonce for a group of that order. It draws as FIPS 186-5
A.2.2 says: the leftmost bits of a draw as long as `order`, drawn again while
the value is zero or not below `order`. A P-521 scalar is 66 bytes with the top
bits clear, which is why this is not "ask for 32 bytes".

```moonbit
test "a P-256 scalar" {
  let order = b"\xff\xff\xff\xff\x00\x00\x00\x00\xff\xff\xff\xff\xff\xff\xff\xff\xbc\xe6\xfa\xad\xa7\x17\x9e\x84\xf3\xb9\xca\xc2\xfc\x63\x25\x51"
  let source = @moonseed.Replay::new(b"\xe4\xb8\x51\x7f\x20\xec\x48\x11\xf7\xd9\xe0\xcf\xa2\xec\x7e\x28\x19\x8a\x34\x1d\xec\xe5\xf7\x7a\x8d\x98\x88\x59\xb9\x44\x62\x41")
  assert_eq(
    @moonseed.scalar(order, source),
    b"\xe4\xb8\x51\x7f\x20\xec\x48\x11\xf7\xd9\xe0\xcf\xa2\xec\x7e\x28\x19\x8a\x34\x1d\xec\xe5\xf7\x7a\x8d\x98\x88\x59\xb9\x44\x62\x41",
  )
  assert_eq(source.remaining(), 0)
}
```

## Licence

Apache-2.0.
