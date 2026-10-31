<div align="center">

<h1>moonseed</h1>

<p><b>Secure random bytes, and numbers drawn from them without bias, over any entropy source the caller supplies.</b></p>

<p>
<a href="https://moonbitstack.github.io/moonseed/">Home</a> ·
<a href="https://moonbitstack.github.io/moonseed/#start">Guide</a> ·
<a href="https://moonbitstack.github.io/moonseed/#api">API</a> ·
<a href="https://mooncakes.io/docs/moonbitstack/moonseed">mooncakes</a>
</p>

</div>

```moonbit
test "draw" {
  let key = @moonseed.bytes(32, @system.source) // 32 uniform bytes
  let n = @moonseed.below(b"\x03\xe8", @system.source) // uniform in [0, 1000)
  let d = @moonseed.scalar(b"\x05", @system.source) // uniform in [1, 4]
  ignore((key, n, d))
}
```

`moon run src/examples/tour` shows all of it in one run.

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

```moonbit
struct Device {}

impl @moonseed.Source for Device with fn fill(_self, _buf) {
  raise Failed("the device is unplugged")
}
```

No source falls back to a seeded generator. When there are no bytes to be had,
the call raises `Unavailable`: `Platform` from the platform source, `Exhausted`
from a replay, `Failed(reason)` from a source of your own. A key drawn from a
fallback looks like any other key and is guessable, so the failure is the
caller's to see.

## Replaying bytes

`Replay` hands out the bytes it was built from, in order, and then raises
`Exhausted`. A test pins a draw with it, and a vector written elsewhere replays
through it byte for byte.

```moonbit
test "replay" {
  let source = @moonseed.Replay::new(b"\x07\xff\x02")
  assert_eq(@moonseed.below(b"\x0a", source), b"\x07")
  // 0xff is 15 once the high bits are cleared, too big, so the next byte is drawn.
  assert_eq(@moonseed.below(b"\x0a", source), b"\x02")
  assert_eq(source.remaining(), 0)
  let refused = try {
    ignore(@moonseed.below(b"\x0a", source))
    false
  } catch {
    Exhausted => true
    _ => false
  }
  assert_true(refused)
}
```

## Sampling

`below(bound, source)` reads `bound` as a big-endian number and returns one in
[0, `bound`), as wide as `bound`. It draws as many bytes as `bound - 1` needs,
clears the unused high bits of the first, and draws again while the value is at
or above `bound`. Every value is equally
likely; reducing a wider draw modulo `bound` would favour the small ones.

`scalar(order, source)` returns a value in [1, `order` - 1], as wide as `order`:
a private key or a nonce for a group of that order. It draws as FIPS 186-5
A.2.2 says: the leftmost bits of a draw as long as `order`, drawn again while
the value is zero or not below `order`. A P-521 scalar is 66 bytes
with the top bits clear, which is why this is not "ask for 32 bytes".

## Licence

Apache-2.0.
