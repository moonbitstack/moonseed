///|
/// `n` uniform random bytes, no more and no fewer.
///
/// Aborts on a negative `n`: that is a mistake in the caller, and handing back
/// an empty buffer would hide it.
///
/// ```mbt check
/// test {
///   let source = @moonseed.Replay::new(b"\x01\x02\x03")
///   assert_eq(@moonseed.bytes(2, source), b"\x01\x02")
/// }
/// ```
pub fn[S : Source] bytes(n : Int32, source : S) -> Bytes raise Unavailable {
  if n < 0 {
    abort("moonseed.bytes: a negative length, \{n}")
  }
  let buf = FixedArray::make(n, b'\x00')
  source.fill(buf)
  Bytes::from_array(buf[:])
}

///|
/// A uniform number in [0, `bound`), big-endian and as wide as `bound`.
///
/// Draws as many bytes as `bound - 1` needs, clears the unused high bits of the
/// first, and draws again while the value is at or above `bound`. Rejection
/// rather than modulo: reducing a wider draw modulo `bound` would favour the
/// small values. A `bound` of 1 reads nothing. Aborts when `bound` is zero.
///
/// ```mbt check
/// test {
///   let source = @moonseed.Replay::new(b"\x17\x90")
///   assert_eq(@moonseed.below(b"\x03\xe8", source), b"\x03\x90")
/// }
/// ```
pub fn[S : Source] below(
  bound : BytesView,
  source : S,
) -> Bytes raise Unavailable {
  let width = bound.length()
  let digits = significant(bound)
  if digits.length() == 0 {
    abort("moonseed.below: the bound is zero")
  }
  let top = minus_one(digits)
  let bits = bit_length(top[:])
  let out = FixedArray::make(width, b'\x00')
  if bits == 0 {
    return Bytes::from_array(out[:])
  }
  let k = (bits + 7) / 8
  let mask = (1 << (if bits % 8 == 0 { 8 } else { bits % 8 })) - 1
  let draw = FixedArray::make(k, b'\x00')
  while true {
    source.fill(draw)
    draw[0] = (draw[0].to_int() & mask).to_byte()
    if less(draw, digits) {
      break
    }
  }
  for i in 0..<k {
    out[width - k + i] = draw[i]
  }
  Bytes::from_array(out[:])
}

///|
/// A uniform number in [1, `order` - 1], as wide as `order`: the private key or
/// nonce of a group of that order.
///
/// Draws as FIPS 186-5 A.2.2 says: the leftmost bits of a draw as long as
/// `order`, drawn again while the value is zero or at or above `order`. A
/// P-521 scalar is 66 bytes with its top bits clear, which is why this cannot
/// be "ask for 32 bytes". Aborts when `order` is below 2.
///
/// ```mbt check
/// test {
///   let source = @moonseed.Replay::new(b"\xc0\x80")
///   assert_eq(@moonseed.scalar(b"\x05", source), b"\x04")
/// }
/// ```
pub fn[S : Source] scalar(
  order : BytesView,
  source : S,
) -> Bytes raise Unavailable {
  let width = order.length()
  let digits = significant(order)
  if digits.length() == 0 || (digits.length() == 1 && digits[0] < b'\x02') {
    abort("moonseed.scalar: the order is below 2")
  }
  let size = digits.length()
  let excess = size * 8 - bit_length(digits)
  let draw = FixedArray::make(size, b'\x00')
  while true {
    source.fill(draw)
    if excess > 0 {
      shift_right(draw, excess)
    }
    if !draw.iter().all(x => x == b'\x00') && less(draw, digits) {
      break
    }
  }
  let out = FixedArray::make(width, b'\x00')
  for i in 0..<size {
    out[width - size + i] = draw[i]
  }
  Bytes::from_array(out[:])
}

///|
/// `b` without its leading zero bytes.
fn significant(b : BytesView) -> BytesView {
  let mut lead = 0
  while lead < b.length() && b[lead] == b'\x00' {
    lead += 1
  }
  b[lead:]
}

///|
/// `b - 1` for a nonzero big-endian `b`, as wide as `b`.
fn minus_one(b : BytesView) -> Bytes {
  let out = FixedArray::makei(b.length(), i => b[i])
  let mut i = out.length() - 1
  while out[i] == b'\x00' {
    out[i] = b'\xff'
    i -= 1
  }
  out[i] = (out[i].to_int() - 1).to_byte()
  Bytes::from_array(out[:])
}

///|
/// The number of bits a big-endian number needs; 0 for zero.
fn bit_length(b : BytesView) -> Int32 {
  for i in 0..<b.length() {
    let x = b[i].to_int()
    if x != 0 {
      return (b.length() - i) * 8 - x.clz() + 24
    }
  }
  0
}

///|
/// Whether `a` is less than `b`, both big-endian; `b` is at least as long as `a`
/// once its leading zeros are gone.
fn less(a : FixedArray[Byte], b : BytesView) -> Bool {
  if b.length() > a.length() {
    return true
  }
  for i in 0..<a.length() {
    if a[i] != b[i] {
      return a[i] < b[i]
    }
  }
  false
}

///|
/// Shift a big-endian number right by 1 to 7 bits in place, keeping its
/// leftmost bits: Go's `rightShift` in `crypto/internal/fips140/ecdsa`.
fn shift_right(b : FixedArray[Byte], shift : Int32) -> Unit {
  for i = b.length() - 1; i >= 0; i = i - 1 {
    let mut v = b[i].to_int() >> shift
    if i > 0 {
      v = v | ((b[i - 1].to_int() << (8 - shift)) & 0xFF)
    }
    b[i] = v.to_byte()
  }
}
