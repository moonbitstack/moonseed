///|
/// The platform's entropy source. It holds nothing; every `fill` asks the
/// platform again.
pub struct System {}

///|
/// The one value there is a need for.
pub let source : System = System::{ }

///|
/// Fails with `Platform` when the platform has no source or reports a failure,
/// and never falls back to anything else.
pub impl @moonseed.Source for System with fn fill(_self, buf) {
  guard @env.rand(buf.length()) is Some(got) && got.length() == buf.length() else {
    raise @moonseed.Unavailable::Platform
  }
  for i in 0..<buf.length() {
    buf[i] = got[i]
  }
}

///|
pub extend System with @moonseed.Source::{fill}
