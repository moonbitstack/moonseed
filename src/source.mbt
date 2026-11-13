///|
/// Where the bytes come from.
///
/// Open, so a program can plug in a hardware source, a service, or a fixed
/// sequence in a test, and this library needs to know about none of them. The
/// platform's own source is `@system.source`.
///
/// ```mbt check
/// test {
///   let source = @moonseed.Replay::new(b"\x2a\x2b")
///   let buf = FixedArray::make(2, b'\x00')
///   source.fill(buf)
///   assert_eq(buf, [b'\x2a', b'\x2b'])
/// }
/// ```
pub(open) trait Source {
  /// Fill all of `buf`, or raise. A source that fills part of it and returns
  /// has broken the contract: the caller has no way to tell how much is real.
  fn fill(Self, FixedArray[Byte]) -> Unit raise Unavailable
}

///|
/// No random bytes could be had. There is no fallback to a seeded generator:
/// a caller that needs entropy and gets none stops here.
///
/// The three cases are told apart because they call for different answers: a
/// platform without a source cannot be retried, a spent replay is a mistake in
/// the test, and a failed source names its own reason.
///
/// ```mbt check
/// test {
///   let spent = try {
///     ignore(@moonseed.bytes(1, @moonseed.Replay::new(b"")))
///     None
///   } catch {
///     e => Some(e)
///   }
///   assert_eq(spent, Some(@moonseed.Unavailable::Exhausted))
///   assert_eq(
///     @moonseed.Unavailable::Failed("no entropy left").to_string(),
///     "no entropy left",
///   )
/// }
/// ```
#derive(Eq, Debug)
pub(all) suberror Unavailable {
  /// The platform has no entropy source, or its source failed.
  Platform
  /// A `Replay` source has given all the bytes it holds.
  Exhausted
  /// A source of the program's own failed, for the reason given.
  Failed(String)
}

///|
pub extend Unavailable with Eq::{equal, not_equal}

///|
pub extend Unavailable with Debug::{to_repr}

///|
pub impl Show for Unavailable with fn output(self, logger) {
  logger.write_string(
    match self {
      Platform => "the platform has no entropy source"
      Exhausted => "the replay source is exhausted"
      Failed(reason) => reason
    },
  )
}

///|
pub extend Unavailable with Show::{to_string, output}
