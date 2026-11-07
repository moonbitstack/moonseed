///|
test "bytes takes exactly n from the source" {
  let source = @moonseed.Replay::new(b"\x01\x02\x03\x04")
  assert_eq(@moonseed.bytes(3, source), b"\x01\x02\x03")
  assert_eq(source.remaining(), 1)
  assert_eq(@moonseed.bytes(0, source), b"")
  let refused = try {
    ignore(@moonseed.bytes(2, source))
    None
  } catch {
    e => Some(e)
  }
  assert_eq(refused, Some(@moonseed.Unavailable::Exhausted))
}

///|
/// The bound as the fewest big-endian bytes that hold it.
fn bound_of(n : Int32) -> Bytes {
  let out = []
  let mut v = n
  while v > 0 {
    out.insert(0, (v & 0xFF).to_byte())
    v = v >> 8
  }
  Bytes::from_array(out)
}

///|
fn int_of(b : Bytes) -> Int32 {
  b.iter().fold(init=0, (acc, x) => acc * 256 + x.to_int())
}

///|
/// Go's `TestIntReads`: a power-of-two bound reads exactly the bytes its
/// largest value needs.
test "below reads as many bytes as the bound's largest value needs" {
  for i in 0..<31 {
    let source = @moonseed.Replay::new(b"\x00\x00\x00\x00\x00\x00\x00\x00")
    ignore(@moonseed.below(bound_of(1 << i), source))
    assert_eq(8 - source.remaining(), (i + 7) / 8)
  }
}

///|
/// Go's `TestIntMask`: a single byte in range comes back unchanged.
test "below returns a byte in range as it was drawn" {
  for max in 1..<=256 {
    for i in 0..<max {
      let source = @moonseed.Replay::new(Bytes::from_array([i.to_byte()]))
      let got = @moonseed.below(bound_of(max), source)
      assert_eq(int_of(got), i)
    }
  }
}

///|
/// Go's `TestInt`, over a source that never refuses.
test "below over the platform for bounds of a whole and a part byte" {
  for n in 128..<140 {
    let got = @moonseed.below(bound_of(n), Counter::{ })
    assert_true(int_of(got) < n)
  }
}

///|
/// The root package has no platform source, so its tests carry a stand-in that
/// never refuses: bytes from a counter run through a mixing step.
priv struct Counter {}

///|
let state : Ref[UInt64] = Ref(0x9E3779B97F4A7C15)

///|
impl @moonseed.Source for Counter with fn fill(_self, buf) {
  for i in 0..<buf.length() {
    state.val = state.val * 6364136223846793005 + 1442695040888963407
    buf[i] = (state.val >> 56).to_byte()
  }
}

///|
test "below keeps the bound's width and leading zeros" {
  let got = @moonseed.below(b"\x00\x05", @moonseed.Replay::new(b"\x04"))
  assert_eq(got, b"\x00\x04")
}

///|
test "below draws again on a value at or above the bound" {
  // 1000 needs ten bits, so 0xff 0xff is cut to 0x03 0xff, which is still 1023.
  let source = @moonseed.Replay::new(b"\xff\xff\x03\xe7")
  assert_eq(@moonseed.below(b"\x03\xe8", source), b"\x03\xe7")
  assert_eq(source.remaining(), 0)
}

///|
test "below takes every value in range from the same number of draws" {
  // Over all 256 one-byte draws, each value below 3 is accepted from exactly
  // 64 of them and 3 is never returned: no value is likelier than another.
  let counts = [0, 0, 0, 0]
  let mut refused = 0
  for d in 0..<256 {
    let source = @moonseed.Replay::new(Bytes::from_array([d.to_byte()]))
    try @moonseed.below(b"\x03", source) catch {
      _ => refused += 1
    } noraise {
      v => counts[v[0].to_int()] += 1
    }
  }
  assert_eq(counts, [64, 64, 64, 0])
  assert_eq(refused, 64)
}

///|
test "scalar keeps the leftmost bits and draws again on zero and on the order" {
  // 5 needs three bits, so a draw keeps its top three: 0x00 is zero, 0xc0 is 6,
  // and 0x80 is 4.
  let source = @moonseed.Replay::new(b"\x00\xc0\x80")
  assert_eq(@moonseed.scalar(b"\x05", source), b"\x04")
  assert_eq(source.remaining(), 0)
}

///|
test "scalar shifts across byte boundaries and is as wide as the order" {
  // 0x01ffff needs seventeen bits: the draw 0x12 0x34 0x56 keeps its top
  // seventeen, which is 0x2468.
  let got = @moonseed.scalar(
    b"\x00\x01\xff\xff",
    @moonseed.Replay::new(b"\x12\x34\x56"),
  )
  assert_eq(got, b"\x00\x00\x24\x68")
}

///|
test "a source of the program's own plugs in" {
  let refused = try {
    ignore(@moonseed.bytes(4, Broken::{ }))
    ""
  } catch {
    e => e.to_string()
  }
  assert_eq(refused, "the device is unplugged")
}

///|
priv struct Broken {}

///|
impl @moonseed.Source for Broken with fn fill(_self, _buf) {
  raise Failed("the device is unplugged")
}

///|
test "messages" {
  assert_eq(
    @moonseed.Unavailable::Platform.to_string(),
    "the platform has no entropy source",
  )
  assert_eq(
    @moonseed.Unavailable::Exhausted.to_string(),
    "the replay source is exhausted",
  )
}

///|
test "panic bytes refuses a negative length" {
  ignore(@moonseed.bytes(-1, @moonseed.Replay::new(b"")))
}

///|
test "panic below refuses a zero bound" {
  ignore(@moonseed.below(b"\x00\x00", @moonseed.Replay::new(b"\x00")))
}

///|
test "panic scalar refuses an order below 2" {
  ignore(@moonseed.scalar(b"\x00\x01", @moonseed.Replay::new(b"\x00")))
}

///|
/// A bound of one has one value below it, and finding it needs no bytes.
test "below of one reads nothing" {
  let source = @moonseed.Replay::new(b"\x00")
  assert_eq(@moonseed.below(b"\x01", source), b"\x00")
  assert_eq(source.remaining(), 1)
}

///|
/// The order itself is refused, not only the values above it: 5 keeps the top
/// three bits of every draw, and 0xa0 keeps 5.
test "scalar draws again on a value equal to the order" {
  let source = @moonseed.Replay::new(b"\xa0\x80")
  assert_eq(@moonseed.scalar(b"\x05", source), b"\x04")
  assert_eq(source.remaining(), 0)
}

///|
/// The mask leaves the top bits of the first byte alone when the bound needs
/// all eight of them: 255 needs no redraw for any draw below it.
test "below a whole byte masks nothing" {
  for d in 0..<255 {
    let source = @moonseed.Replay::new(Bytes::from_array([d.to_byte()]))
    assert_eq(
      @moonseed.below(b"\xff", source),
      Bytes::from_array([d.to_byte()]),
    )
    assert_eq(source.remaining(), 0)
  }
}
