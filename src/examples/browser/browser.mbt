///|
/// The page's door into the library. It holds the bytes the page brought and
/// hands them to `Replay`; every index the page shows is drawn by
/// `@moonseed.below` — or, for the comparison bars, by the raw modulo the page
/// asked for — over that same replay.
///
/// The platform source is not used here on purpose: a wasm-gc host has no
/// `random_get`, so `@system.source` fails closed rather than invent bytes.
/// Gathering bytes is the page's business; turning them into unbiased indices
/// is this library's.
let pool : FixedArray[Byte] = FixedArray::make(16384, b'\x00')

///|
let filled : Array[Int32] = [0]

///|
/// The tile's own replay, so its strokes advance one stream while each plot
/// starts from the front.
let live : Array[@moonseed.Replay] = []

///|
/// Forget every byte pushed so far.
pub fn reset() -> Unit {
  filled[0] = 0
  live.clear()
}

///|
/// Add one byte. The page pushes a few thousand of these at load.
pub fn push(b : Int32) -> Unit {
  if filled[0] < pool.length() {
    pool[filled[0]] = b.to_byte()
    filled[0] = filled[0] + 1
  }
}

///|
/// A fresh replay over the bytes pushed so far.
fn replay() -> @moonseed.Replay {
  @moonseed.Replay::new(Bytes::from_array(pool[:filled[0]]))
}

///|
/// How many bytes the page has given.
pub fn taken() -> Int32 {
  filled[0]
}

///|
/// Restart the tile's stream at the front of the pool.
pub fn open() -> Int32 {
  live.clear()
  live.push(replay())
  filled[0]
}

///|
/// The next byte, as a number in [0, 1), drawn through `below(256)` so the page
/// never reasons about a mask itself. Past the end of the pool it reports the
/// middle value rather than pretending.
pub fn unit() -> Double {
  if live.length() == 0 {
    return 0.5
  }
  let v = @moonseed.below(b"\x01\x00", live[0]) catch { _ => return 0.5 }
  (v[0].to_int() * 256 + v[1].to_int()).to_double() / 256.0
}

///|
/// How many of `trials` draws of `below(upper)` land in bucket `bin` of `bins`
/// equal buckets over [0, `upper`). Every bucket counts the same run: the
/// replay starts at the front each time, so the bars partition one sample.
pub fn below_hits(
  upper : Int32,
  trials : Int32,
  bin : Int32,
  bins : Int32,
) -> Int32 {
  if upper <= 0 || bins <= 0 || trials <= 0 || filled[0] == 0 {
    return 0
  }
  let width = if upper % bins == 0 { upper / bins } else { upper / bins + 1 }
  let bound = bound_bytes(upper)
  let src = replay()
  let mut hits = 0
  for _i = 0; _i < trials; _i = _i + 1 {
    let v = bound_value(@moonseed.below(bound[:], src)) catch { _ => break }
    if v / width == bin {
      hits = hits + 1
    }
  }
  hits
}

///|
/// The same count, but by reducing one raw byte modulo `upper`: the biased draw
/// `below` exists to avoid. Same replay, same number of draws.
pub fn mod_hits(
  upper : Int32,
  trials : Int32,
  bin : Int32,
  bins : Int32,
) -> Int32 {
  if upper <= 0 || bins <= 0 || trials <= 0 || filled[0] == 0 {
    return 0
  }
  let width = if upper % bins == 0 { upper / bins } else { upper / bins + 1 }
  let src = replay()
  let one = FixedArray::make(1, b'\x00')
  let mut hits = 0
  for _i = 0; _i < trials; _i = _i + 1 {
    let v = try {
      src.fill(one)
      one[0].to_int() % upper
    } catch {
      _ => break
    }
    if v / width == bin {
      hits = hits + 1
    }
  }
  hits
}

///|
/// `n` as a big-endian bound, four bytes wide: what `below` reads.
fn bound_bytes(n : Int32) -> Bytes {
  let out = FixedArray::make(4, b'\x00')
  out[0] = ((n >> 24) & 0xFF).to_byte()
  out[1] = ((n >> 16) & 0xFF).to_byte()
  out[2] = ((n >> 8) & 0xFF).to_byte()
  out[3] = (n & 0xFF).to_byte()
  Bytes::from_array(out[:])
}

///|
/// The same number read back out of four big-endian bytes.
fn bound_value(b : Bytes) -> Int32 {
  let mut v = 0
  for i in 0..<b.length() {
    v = (v << 8) | b[i].to_int()
  }
  v
}

///|
/// What one call to `below` did, for the bench: the bound, the width it drew,
/// the mask it applied, how many attempts it took, and the value it returned.
/// Every number here comes from the call; the page only lays them out.
let trace_state : Array[Int32] = [0, 0, 0, 0, 0]

///|
/// The bytes the call consumed, in the order the replay gave them.
let trace_bytes : Array[Int32] = []

///|
/// The order of the P-521 group: sixty-six bytes, 521 bits, seven spare.
let p521_order : Bytes = b"\x01\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xfa\x51\x86\x87\x83\xbf\x2f\x96\x6b\x7f\xcc\x01\x48\xf7\x09\xa5\xd0\x3b\xb5\xc9\xb8\x89\x9c\x47\xae\xbb\x6f\xb7\x1e\x91\x38\x64\x09"

///|
let scalar_bytes : Array[Int32] = []

///|
/// Run one `below` over a fresh replay and keep what it did. Returns 1 when
/// it returned a number, 0 when the pool had no bytes left to give.
pub fn trace(bound : Int32) -> Int32 {
  trace_bytes.clear()
  if bound < 2 {
    return 0
  }
  let digits = bound - 1
  let bits = 32 - digits.clz()
  let width = (bits + 7) / 8
  trace_state[0] = bound
  trace_state[1] = width
  trace_state[2] = (1 << (if bits % 8 == 0 { 8 } else { bits % 8 })) - 1
  let src = replay()
  let before = src.remaining()
  let got = @moonseed.below(bound_bytes(bound)[:], src) catch { _ => return 0 }
  let consumed = before - src.remaining()
  trace_state[3] = consumed / width
  trace_state[4] = bound_value(got)
  for i in 0..<consumed {
    trace_bytes.push(pool[i].to_int())
  }
  1
}

///|
pub fn trace_width() -> Int32 {
  trace_state[1]
}

///|
pub fn trace_mask() -> Int32 {
  trace_state[2]
}

///|
pub fn trace_attempts() -> Int32 {
  trace_state[3]
}

///|
pub fn trace_value() -> Int32 {
  trace_state[4]
}

///|
pub fn trace_byte(i : Int32) -> Int32 {
  if i < 0 || i >= trace_bytes.length() {
    return -1
  }
  trace_bytes[i]
}

///|
/// Draw one P-521 scalar from a fresh replay. Returns 1 when one came back.
pub fn scalar_draw() -> Int32 {
  scalar_bytes.clear()
  let src = replay()
  let got = @moonseed.scalar(p521_order[:], src) catch { _ => return 0 }
  for b in got {
    scalar_bytes.push(b.to_int())
  }
  1
}

///|
pub fn scalar_len() -> Int32 {
  scalar_bytes.length()
}

///|
pub fn scalar_byte(i : Int32) -> Int32 {
  if i < 0 || i >= scalar_bytes.length() {
    return -1
  }
  scalar_bytes[i]
}

///|
fn main {
  ignore(unit)
}
