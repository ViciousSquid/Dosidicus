"""Meeting a friend's squid over the internet: friend codes and direct links.

On a home network two tanks find each other by themselves (multicast). Across
the internet nothing finds anything: one player has to tell the other where
their tank is. This module is the "where" - and nothing else. It is pure:
no sockets are opened here and nothing is sent.

    FRIEND CODE   Twenty letters and digits, e.g.  4KQ7M-2D0HX-9T1VB-C3F8A
                  It says three things: the address the tank can be reached
                  at from outside, the port, and an INVITATION - a number only
                  someone holding the code knows. A tank answers a stranger on
                  the internet only if the stranger shows its invitation.

    DIRECT IP     The same without the invitation: `203.0.113.7` or
                  `203.0.113.7:10000`. Because no invitation is shown, the
                  other player has to add YOUR address too before either tank
                  will listen to the other.

What a friend code gives away: the public address of the player's connection,
to whoever they hand it to. It is found by asking a public "what is my
address?" server (STUN) once, when the player asks for a code - never before.

Getting through a home router. A router lets in traffic only from somewhere
the tank has itself just sent to. So the link comes up when EITHER
  * both players enter each other's code (each tank sends first, and each
    router then lets the other's traffic in - "hole punching"), or
  * the player being joined has forwarded the UDP port on their router.
Some routers (ones that give every destination a different outside port)
defeat the first; the second always works.
"""
from __future__ import annotations

import ipaddress
import os
import re
import struct
from dataclasses import dataclass
from typing import Optional, Tuple

DEFAULT_PORT = 10000

#: Crockford's alphabet: no I, L, O or U, so a code read aloud or copied by
#: hand does not turn into a different one.
_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_DECODE = {char: index for index, char in enumerate(_ALPHABET)}
_DECODE.update({'I': 1, 'L': 1, 'O': 0})        # what people actually type
_CODE_VERSION = 1
_CODE_BYTES = 12        # version, 4 address, 2 port, 4 invitation, 1 check


class FriendCodeError(ValueError):
    """The text is not a friend code or an address this game can use."""


@dataclass(frozen=True)
class Whereabouts:
    """Where a friend's tank is, and the invitation to it if we hold one."""
    ip: str
    port: int = DEFAULT_PORT
    invitation: int = 0

    @property
    def address(self) -> Tuple[str, int]:
        return self.ip, self.port


def new_invitation() -> int:
    """A fresh 32-bit invitation. Never zero: zero means "none"."""
    while True:
        value = struct.unpack('>I', os.urandom(4))[0]
        if value:
            return value


def _checksum(body: bytes) -> int:
    total = 0x5A
    for byte in body:
        total = (total * 31 + byte) & 0xFF
    return total


def encode_friend_code(ip: str, port: int, invitation: int) -> str:
    """The friend code for a tank at ip:port, with this invitation."""
    try:
        packed_ip = ipaddress.IPv4Address(ip).packed
    except ipaddress.AddressValueError as exc:
        raise FriendCodeError(f"not an IPv4 address: {ip!r}") from exc
    if not 0 < int(port) < 65536:
        raise FriendCodeError(f"not a port: {port!r}")
    body = (bytes([_CODE_VERSION]) + packed_ip + struct.pack('>H', int(port))
            + struct.pack('>I', int(invitation) & 0xFFFFFFFF))
    raw = body + bytes([_checksum(body)])
    number = int.from_bytes(raw, 'big')
    chars = []
    for _ in range(20):                    # 12 bytes = 96 bits -> 20 x 5 bits
        chars.append(_ALPHABET[number & 31])
        number >>= 5
    text = ''.join(reversed(chars))
    return '-'.join(text[i:i + 5] for i in range(0, 20, 5))


def decode_friend_code(text: str) -> Whereabouts:
    """Read a friend code. Spaces, dashes and lower case are all forgiven."""
    cleaned = re.sub(r'[\s\-_.]', '', str(text or '')).upper()
    if len(cleaned) != 20:
        raise FriendCodeError("a friend code is 20 letters and digits")
    number = 0
    for char in cleaned:
        if char not in _DECODE:
            raise FriendCodeError(f"{char!r} is not used in friend codes")
        number = (number << 5) | _DECODE[char]
    if number >> (_CODE_BYTES * 8):
        raise FriendCodeError("that is not a friend code")
    raw = number.to_bytes(_CODE_BYTES, 'big')
    body, check = raw[:-1], raw[-1]
    if _checksum(body) != check:
        raise FriendCodeError("that code has a mistake in it - check it "
                              "against the one you were given")
    if body[0] != _CODE_VERSION:
        raise FriendCodeError("that code was made by a different version of the game")
    ip = str(ipaddress.IPv4Address(body[1:5]))
    port = struct.unpack('>H', body[5:7])[0]
    invitation = struct.unpack('>I', body[7:11])[0]
    if not port:
        raise FriendCodeError("that is not a friend code")
    return Whereabouts(ip, port, invitation)


def parse_friend(text: str) -> Whereabouts:
    """A friend code, or an address typed by hand: `1.2.3.4` or `1.2.3.4:10000`."""
    entered = str(text or '').strip()
    if not entered:
        raise FriendCodeError("enter a friend code or an IP address")
    match = re.fullmatch(r'(\d{1,3}(?:\.\d{1,3}){3})(?::(\d{1,5}))?', entered)
    if match:
        try:
            ip = str(ipaddress.IPv4Address(match.group(1)))
        except ipaddress.AddressValueError as exc:
            raise FriendCodeError(f"{match.group(1)} is not an IP address") from exc
        port = int(match.group(2)) if match.group(2) else DEFAULT_PORT
        if not 0 < port < 65536:
            raise FriendCodeError(f"{port} is not a port")
        return Whereabouts(ip, port, 0)
    return decode_friend_code(entered)


def is_local_address(ip: str) -> bool:
    """On this machine or this home network - where tanks have always simply
    heard each other, and still do."""
    try:
        address = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return bool(address.is_private or address.is_loopback or address.is_link_local)


# ---------------------------------------------------------------------------
# STUN (RFC 5389): "what address do you see me coming from?"
# ---------------------------------------------------------------------------
STUN_MAGIC = 0x2112A442
_STUN_REQUEST = 0x0001
_STUN_SUCCESS = 0x0101
_XOR_MAPPED_ADDRESS = 0x0020
_MAPPED_ADDRESS = 0x0001


def stun_request(transaction_id: Optional[bytes] = None) -> bytes:
    """A binding request. Twenty bytes, carrying nothing about the player."""
    transaction_id = transaction_id or os.urandom(12)
    if len(transaction_id) != 12:
        raise ValueError("a STUN transaction id is 12 bytes")
    return struct.pack('>HHI', _STUN_REQUEST, 0, STUN_MAGIC) + transaction_id


def looks_like_stun(datagram: bytes) -> bool:
    return (len(datagram) >= 20 and datagram[0] < 4
            and struct.unpack('>I', datagram[4:8])[0] == STUN_MAGIC)


def stun_mapped_address(datagram: bytes) -> Optional[Tuple[str, int]]:
    """The (ip, port) a STUN server says it saw, or None if this is not an
    answer that says so."""
    if not looks_like_stun(datagram):
        return None
    kind, length = struct.unpack('>HH', datagram[:4])
    if kind != _STUN_SUCCESS:
        return None
    end = min(len(datagram), 20 + length)
    offset, plain = 20, None
    while offset + 4 <= end:
        attribute, size = struct.unpack('>HH', datagram[offset:offset + 4])
        value = datagram[offset + 4:offset + 4 + size]
        if len(value) >= 8 and value[1] == 0x01:          # IPv4
            port, raw_ip = struct.unpack('>H', value[2:4])[0], value[4:8]
            if attribute == _XOR_MAPPED_ADDRESS:
                port ^= STUN_MAGIC >> 16
                number = struct.unpack('>I', raw_ip)[0] ^ STUN_MAGIC
                return str(ipaddress.IPv4Address(number)), port
            if attribute == _MAPPED_ADDRESS:
                plain = (str(ipaddress.IPv4Address(raw_ip)), port)
        offset += 4 + size + ((4 - size % 4) % 4)
    return plain


__all__ = ['DEFAULT_PORT', 'FriendCodeError', 'Whereabouts', 'new_invitation',
           'encode_friend_code', 'decode_friend_code', 'parse_friend',
           'is_local_address', 'stun_request', 'looks_like_stun',
           'stun_mapped_address', 'STUN_MAGIC']
