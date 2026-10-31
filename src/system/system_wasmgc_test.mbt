///|
/// The wasm-gc test host provides no `random_get`, so the platform source
/// fails closed there rather than handing out anything.
test "without a platform source the answer is Platform, not bytes" {
  let got = Some(@moonseed.bytes(32, @system.source)) catch {
    e => {
      assert_eq(e, @moonseed.Unavailable::Platform)
      None
    }
  }
  assert_eq(got, None)
}
