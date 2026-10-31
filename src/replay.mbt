///|
/// A source that hands out the bytes it was given, in order, and is exhausted
/// after: the fixed randomness of a test vector, or a test that walks every
/// branch of a rejection loop.
pub struct Replay {
  priv data : Bytes
  priv mut at : Int32
}

///|
pub fn Replay::new(data : Bytes) -> Replay {
  { data, at: 0, }
}

///|
/// How many bytes are left to give.
pub fn Replay::remaining(self : Replay) -> Int32 {
  self.data.length() - self.at
}

///|
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
