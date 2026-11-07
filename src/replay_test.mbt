///|
/// A fill that wants more than is left takes nothing: the buffer keeps what it
/// had and the source keeps every byte it still holds.
test "a short fill leaves the buffer and the byte count alone" {
  let source = @moonseed.Replay::new(b"\x01\x02\x03")
  let buf = FixedArray::make(4, b'\x7f')
  let refused = try {
    source.fill(buf)
    false
  } catch {
    @moonseed.Unavailable::Exhausted => true
    _ => false
  }
  assert_true(refused)
  assert_eq(buf, [b'\x7f', b'\x7f', b'\x7f', b'\x7f'])
  assert_eq(source.remaining(), 3)
}

///|
/// Fills that add up to the whole replay are served; the one after that is
/// refused, and a fill of nothing is always served.
test "the replay is spent by the byte, not by the fill" {
  let source = @moonseed.Replay::new(b"\x0a\x0b\x0c")
  let first = FixedArray::make(2, b'\x00')
  source.fill(first)
  assert_eq(first, [b'\x0a', b'\x0b'])
  assert_eq(source.remaining(), 1)
  let last = FixedArray::make(1, b'\x00')
  source.fill(last)
  assert_eq(last, [b'\x0c'])
  assert_eq(source.remaining(), 0)
  let empty = FixedArray::make(0, b'\x00')
  source.fill(empty)
  assert_eq(source.remaining(), 0)
}

///|
/// A replay of no bytes gives none of them, and says so the first time it is
/// asked for one.
test "an empty replay refuses at the first byte and before" {
  let source = @moonseed.Replay::new(b"")
  assert_eq(source.remaining(), 0)
  let refused = try {
    ignore(@moonseed.bytes(1, source))
    false
  } catch {
    @moonseed.Unavailable::Exhausted => true
    _ => false
  }
  assert_true(refused)
  assert_eq(@moonseed.bytes(0, source), b"")
}
