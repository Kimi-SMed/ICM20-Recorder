"""AES-128 CBC/ECB encryption + CRC16 + CryptionMessage CTR mode for ICM2 BLE handshake.
Copied byte-identical from ICM-GEN2-PC-FWIT/ATSPythonBackend/command_encryption.py.
DO NOT modify - protocol depends on exact bit-for-bit behavior."""

import os
import copy
import crcmod
import logging
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes


ECB_BUF_LENGTH = 16


def encrypt_CBC(key: bytearray, plaintext: bytearray):
    iv = bytearray([0] * 16)
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    encryptor = cipher.encryptor()
    ciphertext = encryptor.update(plaintext) + encryptor.finalize()
    return bytearray(ciphertext)


def decrypt_CBC(key, ciphertext):
    iv = bytearray([0] * 16)
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    decryptor = cipher.decryptor()
    decrypted_data = decryptor.update(ciphertext) + decryptor.finalize()
    return bytearray(decrypted_data)


def encrypt_ECB(key, plaintext:bytearray):
    cipher = Cipher(algorithms.AES(key), modes.ECB(), backend=default_backend())
    encryptor = cipher.encryptor()
    ciphertext = encryptor.update(plaintext) + encryptor.finalize()
    return ciphertext


def decrypt_ECB(key, ciphertext:bytearray):
    cipher = Cipher(algorithms.AES(key), modes.ECB(), backend=default_backend())
    decryptor = cipher.decryptor()
    plaintext = decryptor.update(ciphertext) + decryptor.finalize()
    return plaintext


def append_crc16(byte_array):
    crc16_func = crcmod.mkCrcFun(0x11021, initCrc=0xFFFF, xorOut=0x0000, rev=False)
    crc_value = crc16_func(byte_array)
    byte_array.extend(crc_value.to_bytes(2, byteorder='little'))


class CryptionMessage:
    def __init__(self, nonce, key):
        self.nonce = nonce
        self.key = key
        self.sendCTR = 0
        self.receiveCTR = 0

    def resetCounter(self):
        self.sendCTR = 0
        self.receiveCTR = 0

    def getNonceCtrBuffer(self, IsSending):
        logging.debug(f"Run getNonceCtrBuffer IsSensing = {IsSending}")
        nonce_ctr_buffer = copy.deepcopy(self.nonce)
        if IsSending:
            nonce_ctr_buffer[0:4] = self.sendCTR.to_bytes(4, byteorder='little')
            # self.sendCTR+=1
        else:
            nonce_ctr_buffer[0:4] = self.receiveCTR.to_bytes(4, byteorder='little')
            # self.receiveCTR += 1
        logging.debug(f"self.sendCTR = {self.sendCTR}, self.receiveCTR = {self.receiveCTR}")
        logging.debug(f"nonce_ctr_buffer = {list(map(int, nonce_ctr_buffer))}")
        # print("nonce buffer before encryption is", nonce_ctr_buffer)
        encrypted_nonce_ctr_buffer = encrypt_ECB(self.key,nonce_ctr_buffer)
        logging.debug(f"encrypted_nonce_ctr_buffer = {list(map(int, encrypted_nonce_ctr_buffer))}")
        # print("nonce buffer after encryption is", encrypted_nonce_ctr_buffer)
        return encrypted_nonce_ctr_buffer

    def decryptHelper(self, input):
        logging.debug(f"run decryptHelper, {list(map(int,input))}")
        result = bytearray()
        encrypted_nonce_ctr_buffer = self.getNonceCtrBuffer(IsSending=False)
        for i in range(len(input)):
            result.append(input[i] ^ encrypted_nonce_ctr_buffer[i])
        return result

    def decrypt(self, input):
        # print("before decrypting", input)
        logging.debug("++++++++++++++++++++++++++++++++++++++++++++++++++Start Decrypt")
        lengthLeft = len(input)
        index = 0
        result = bytearray()
        while lengthLeft >= ECB_BUF_LENGTH:
            result.extend(self.decryptHelper(input[0+index:16+index]))
            lengthLeft -= ECB_BUF_LENGTH
            index += ECB_BUF_LENGTH
        if lengthLeft > 0:
            result.extend(self.decryptHelper(input[0 + index:]))
        # print("after decrypting", result)
        logging.debug("++++++++++++++++++++++++++++++++++++++++++++++++++End Decrypt")
        return result

    def encryptHelper(self, input):
        # print("before encrypt", input)
        logging.debug(f"run encryptHelper, {list(map(int,input))}")
        encrypted_nonce_ctr_buffer = self.getNonceCtrBuffer(IsSending=True)
        # print("nonce ctr buffer is", encrypted_nonce_ctr_buffer)
        for i in range(len(input)):
            input[i] ^= encrypted_nonce_ctr_buffer[i]
        # print("after encrypt", input)
        return input

    def encrypt(self, input):
        logging.debug("&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&Start Encrypt")
        lengthLeft = len(input)
        index = 0
        result = bytearray()
        while lengthLeft >= ECB_BUF_LENGTH:
            result.extend(self.encryptHelper(input[0+index:16+index]))
            lengthLeft -= ECB_BUF_LENGTH
            index += ECB_BUF_LENGTH
        if lengthLeft > 0:
            result.extend(self.encryptHelper(input[0 + index:]))
        temp = copy.deepcopy(result)
        # print("temp decrypt is", self.decryptHelper(temp))
        # print("before return", result)
        logging.debug(f"Encrypt result = {list(map(int, result))}")
        logging.debug("&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&End Encrypt")
        return result


if __name__ == "__main__":
    # Example usage
    key = os.urandom(16)  # Generate a random 128-bit key
    plaintext = bytearray(b"1234567891234567")

    # Encrypt the data
    ciphertext = encrypt_CBC(key, plaintext)
    print("Ciphertext:", ciphertext)

    # Decrypt the data
    decrypted_text = decrypt_CBC(key, ciphertext)
    print("Decrypted Text:", decrypted_text.decode('utf-8'))
