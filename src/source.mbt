///|
/// Where random bytes come from: Rust's `RngCore::try_fill_bytes`. The
/// platform's source is `@system.source`; a program implements this for a
/// hardware source, a service, or a fixed sequence in its tests.
pub(open) trait Source {
  fn fill(Self, FixedArray[Byte]) -> Unit raise Unavailable
}

///|
/// No random bytes could be had. There is no fallback to a seeded generator:
/// a caller that needs entropy and gets none stops here.
pub(all) suberror Unavailable {
  /// The platform has no entropy source, or its source failed.
  Platform
  /// A `Replay` source has given all the bytes it holds.
  Exhausted
  /// A source of the program's own failed, for the reason given.
  Failed(String)
} derive(Eq, Debug)

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
