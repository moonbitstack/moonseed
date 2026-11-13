///|
/// The platform's entropy source. It holds nothing; every `fill` asks the
/// platform again.
///
/// Holding nothing is the point: a cached buffer is a copy of the platform's
/// secret that this library would then be responsible for wiping, and a stale
/// one after a fork or a resume.
pub struct System {}

///|
/// The one value there is a need for.
///
/// ```mbt check
/// test {
///   // Nothing to construct and nothing to close: the value carries no state,
///   // and each fill asks the platform again.
///   ignore(@system.source)
/// }
/// ```
pub let source : System = System::{ }

///|
/// Fails with `Platform` when the platform has no source or reports a failure,
/// and never falls back to anything else.
///
/// A host without entropy is a host whose secrets cannot be guessed only by
/// accident; inventing bytes for it would turn that into a silent weakness.
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
