///|
test "the platform gives bytes, and different ones each time" {
  let a = @moonseed.bytes(32, @system.source)
  let b = @moonseed.bytes(32, @system.source)
  assert_eq(a.length(), 32)
  assert_true(a != b)
}

///|
test "sampling over the platform stays in range" {
  for _ in 0..<200 {
    let v = @moonseed.below(b"\x03\xe8", @system.source)
    assert_true(v.length() == 2 && v[0].to_int() * 256 + v[1].to_int() < 1000)
  }
  let d = @moonseed.scalar(b"\x05", @system.source)
  assert_true(d[0] >= b'\x01' && d[0] <= b'\x04')
}
