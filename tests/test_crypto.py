"""Unit tests for ICM2 crypto module (AES-CBC, CRC16, CryptionMessage)."""

import os
import pytest
from icm.crypto import encrypt_CBC, decrypt_CBC, CryptionMessage, append_crc16


class TestAESCBC:
    """Test AES-CBC encryption/decryption round-trip."""

    def test_aes_cbc_roundtrip_zero_key(self):
        """Encrypt and decrypt with all-zero key — should recover plaintext."""
        key = bytearray(16)  # all-zero 128-bit key
        plain = bytearray(b'1234567891234567')  # 16 bytes
        
        ct = encrypt_CBC(key, plain)
        pt = decrypt_CBC(key, ct)
        
        assert pt == plain
        assert len(ct) == 16

    def test_aes_cbc_roundtrip_random_key(self):
        """Encrypt and decrypt with random key — should recover plaintext."""
        key = bytearray(os.urandom(16))
        plain = bytearray(b'Hello_World_Test')  # 16 bytes
        
        ct = encrypt_CBC(key, plain)
        pt = decrypt_CBC(key, ct)
        
        assert pt == plain

    def test_aes_cbc_different_keys_produce_different_ciphertexts(self):
        """Same plaintext encrypted with different keys should produce different ciphertexts."""
        key1 = bytearray(16)  # all zeros
        key2 = bytearray([1] * 16)  # all ones
        plain = bytearray(b'abcdefghijklmnop')
        
        ct1 = encrypt_CBC(key1, plain)
        ct2 = encrypt_CBC(key2, plain)
        
        assert ct1 != ct2

    def test_aes_cbc_32_byte_plaintext(self):
        """Round-trip with 32-byte plaintext (2 blocks)."""
        key = bytearray(os.urandom(16))
        plain = bytearray(b'0123456789abcdef' * 2)  # 32 bytes
        
        ct = encrypt_CBC(key, plain)
        pt = decrypt_CBC(key, ct)
        
        assert pt == plain
        assert len(ct) == 32


class TestCRC16:
    """Test CRC16 append functionality."""

    def test_append_crc16_adds_two_bytes(self):
        """CRC16 should append exactly 2 bytes to the array."""
        data = bytearray([0x01, 0x02, 0x03, 0x04])
        original_len = len(data)
        
        append_crc16(data)
        
        assert len(data) == original_len + 2

    def test_append_crc16_empty_data(self):
        """CRC16 should work on empty data."""
        data = bytearray()
        
        append_crc16(data)
        
        assert len(data) == 2

    def test_append_crc16_deterministic(self):
        """Same data should produce same CRC."""
        data1 = bytearray([0x01, 0x02, 0x03, 0x04])
        data2 = bytearray([0x01, 0x02, 0x03, 0x04])
        
        append_crc16(data1)
        append_crc16(data2)
        
        # Last 2 bytes should be identical (the CRC)
        assert data1[-2:] == data2[-2:]

    def test_append_crc16_different_data_different_crc(self):
        """Different data should produce different CRCs."""
        data1 = bytearray([0x01, 0x02, 0x03, 0x04])
        data2 = bytearray([0xFF, 0xFF, 0xFF, 0xFF])
        
        append_crc16(data1)
        append_crc16(data2)
        
        assert data1[-2:] != data2[-2:]


class TestCryptionMessage:
    """Test CryptionMessage encrypt/decrypt with CTR mode."""

    def test_cryption_message_roundtrip(self):
        """Encrypt then decrypt should recover plaintext."""
        nonce = bytearray(os.urandom(16))
        key = bytearray(os.urandom(16))
        
        cm = CryptionMessage(nonce, key)
        plain = bytearray(b'test_data_123456')  # 16 bytes
        
        encrypted = cm.encrypt(plain.copy())
        
        # Create fresh CryptionMessage with same nonce/key to reset counters
        cm2 = CryptionMessage(nonce, key)
        decrypted = cm2.decrypt(encrypted)
        
        assert decrypted == plain

    def test_cryption_message_different_nonces_differ(self):
        """Same plaintext with different nonces should produce different ciphertexts."""
        nonce1 = bytearray(os.urandom(16))
        nonce2 = bytearray(os.urandom(16))
        key = bytearray(os.urandom(16))
        plain = bytearray(b'same_plaintext__')
        
        cm1 = CryptionMessage(nonce1, key)
        cm2 = CryptionMessage(nonce2, key)
        
        ct1 = cm1.encrypt(plain.copy())
        ct2 = cm2.encrypt(plain.copy())
        
        assert ct1 != ct2

    def test_cryption_message_reset_counter(self):
        """resetCounter() should reset send/receive counters."""
        nonce = bytearray(os.urandom(16))
        key = bytearray(os.urandom(16))
        cm = CryptionMessage(nonce, key)
        
        # Counters should start at 0
        assert cm.sendCTR == 0
        assert cm.receiveCTR == 0
        
        # After reset they should still be 0 (already reset)
        cm.resetCounter()
        assert cm.sendCTR == 0
        assert cm.receiveCTR == 0

    def test_cryption_message_long_data_32_bytes(self):
        """Encrypt/decrypt 32 bytes (2 ECB blocks)."""
        nonce = bytearray(os.urandom(16))
        key = bytearray(os.urandom(16))
        cm = CryptionMessage(nonce, key)
        
        plain = bytearray(b'0123456789abcdef' * 2)  # 32 bytes
        encrypted = cm.encrypt(plain.copy())
        
        cm2 = CryptionMessage(nonce, key)
        decrypted = cm2.decrypt(encrypted)
        
        assert decrypted == plain
