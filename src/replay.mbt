///|
/// A source that hands out the bytes it was given, in order, and is exhausted
/// after.
///
/// Built from bytes alone, so a draw can be pinned to a fixed sequence without
/// a platform in sight: the fixed randomness of a test vector, or a test that
/// walks every branch of a rejection loop.
///
/// ```mbt check
/// test {
///   let source = @moonseed.Replay::new(b"\x0a")
///   let buf = FixedArray::make(1, b'\x00')
///   source.fill(buf)
///   assert_eq(buf, [b'\x0a'])
/// }
/// ```
pub struct Replay {
  priv data : Bytes
  priv mut at : Int32
}

///|
/// Build a source from the bytes a draw should see, in order.
///
/// The bytes are held as given; nothing is copied twice, and nothing is
/// generated when they run out.
///
/// ```mbt check
/// test {
///   let source = @moonseed.Replay::new(b"\x01\x02")
///   assert_eq(source.remaining(), 2)
/// }
/// ```
pub fn Replay::new(data : Bytes) -> Replay {
  { data, at: 0, }
}

///|
/// How many bytes are left to give.
///
/// ```mbt check
/// test {
///   let source = @moonseed.Replay::new(b"\x0a\x0b")
///   let buf = FixedArray::make(1, b'\x00')
///   source.fill(buf)
///   assert_eq(source.remaining(), 1)
/// }
/// ```
pub fn Replay::remaining(self : Replay) -> Int32 {
  self.data.length() - self.at
}

///|
/// Copy the next bytes of the replay into `buf`.
///
/// It refuses whole: when fewer bytes remain than `buf` wants, nothing is
/// copied, `remaining()` is unchanged, and `Exhausted` is raised. A half-filled
/// buffer is the kind of thing a caller forgets to check.
///
/// ```mbt check
/// test {
///   let source = @moonseed.Replay::new(b"\x07\x08")
///   let buf = FixedArray::make(2, b'\x00')
///   source.fill(buf)
///   assert_eq(buf, [b'\x07', b'\x08'])
///   assert_eq(source.remaining(), 0)
/// }
/// ```
pub impl Source for Replay with fn fill(self, buf) {
  if buf.length() > self.remaining() {
    raise Exhausted
  }
  for i in 0..<buf.length() {
    buf[i] = self.data[self.at + i]
  }
  self.at += buf.length()
}

///|
pub extend Replay with Source::{fill}
