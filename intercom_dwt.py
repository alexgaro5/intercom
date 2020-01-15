# Using the Discrete Wavelet Transform, convert the chunks of samples
# intro chunks of Wavelet coefficients (coeffs).
#
# The coefficients require more bitplanes than the original samples,
# but most of the energy of the samples of the original chunk tends to
# be into a small number of coefficients that are localized, usually
# in the low-frequency subbands:
#
# (supposing a chunk with 1024 samples)
#
# Amplitude
#     |       +                      *
#     |   *     *                  *
#     | *        *                *
#     |*          *             *
#     |             *       *
#     |                 *
#     +------------------------------- Time
#     0                  ^        1023 
#                |       |       
#               DWT  Inverse DWT 
#                |       |
#                v
# Amplitude
#     |*
#     |
#     | *
#     |  **
#     |    ****
#     |        *******
#     |               *****************
#     +++-+---+------+----------------+ Frequency
#     0                            1023
#     ^^ ^  ^     ^           ^
#     || |  |     |           |
#     || |  |     |           +--- Subband H1 (16N coeffs)
#     || |  |     +--------------- Subband H2 (8N coeffs)
#     || |  +--------------------- Subband H3 (4N coeffs)
#     || +------------------------ Subband H4 (2N coeffs)
#     |+-------------------------- Subband H5 (N coeffs)
#     +--------------------------- Subband L5 (N coeffs)
#
# (each channel must be transformed independently)
#
# This means that the most-significant bitplanes, for most chunks
# (this depends on the content of the chunk), should have only bits
# different of 0 in the coeffs that belongs to the low-frequency
# subbands. This will be exploited in a future issue.
#
# The straighforward implementation of this issue is to transform each
# chun without considering the samples of adjacent
# chunks. Unfortunately this produces an error in the computation of
# the coeffs that are at the beginning and the end of each subband. To
# compute these coeffs correctly, the samples of the adjacent chunks
# i-1 and i+1 should be used when the chunk i is transformed:
#
#   chunk i-1     chunk i     chunk i+1
# +------------+------------+------------+
# |          OO|OOOOOOOOOOOO|OO          |
# +------------+------------+------------+
#
# O = sample
#
# (In this example, only 2 samples are required from adajact chunks)
#
# The number of ajacent samples depends on the Wavelet
# transform. However, considering that usually a chunk has a number of
# samples larger than the number of coefficients of the Wavelet
# filters, we don't need to be aware of this detail if we work with
# chunks.

import struct
import numpy as np
import pywt
from intercom import Intercom
from intercom_empty import Intercom_empty

#Para ejecutar y que vaya bien en Windows -s 8192 -cb 8
#
wavelet = 'db1'
#
padding = "per"
#
level = 4
#
factor = 10

if __debug__:
    import sys

class Intercom_DWT(Intercom_empty):

    def init(self, args):
        Intercom_empty.init(self, args)
        #
        self.max_NOBPTS = 32*self.number_of_channels

        #
        zeros = np.zeros(self.frames_per_chunk)
        self.coeffs = pywt.wavedec(zeros, wavelet=wavelet, mode=padding, level=level)
        temp, self.coeff_slices = pywt.coeffs_to_array(self.coeffs)

        #
        self.buffer_temp = np.zeros((len(temp), 2), dtype=np.int32)
        self.buffer_coefs = [None]*self.cells_in_buffer

        #
        for i in range(self.cells_in_buffer):
            self.buffer_coefs[i] = np.zeros((self.frames_per_chunk, 2), dtype=np.int32)


    def receive_and_buffer(self):
        message, source_address = self.receiving_sock.recvfrom(Intercom.MAX_MESSAGE_SIZE)
        received_chunk_number, received_bitplane_number, self.NORB, *bitplane = struct.unpack(self.packet_format, message)
        bitplane = np.asarray(bitplane, dtype=np.uint8)
        bitplane = np.unpackbits(bitplane)
        #
        bitplane = bitplane.astype(np.int32)
        self.buffer_coefs[received_chunk_number % self.cells_in_buffer][:, received_bitplane_number%self.number_of_channels] |= (bitplane << received_bitplane_number//self.number_of_channels)
        self.received_bitplanes_per_chunk[received_chunk_number % self.cells_in_buffer] += 1
        return received_chunk_number


    def send(self, indata):
        signs = indata & 0x8000
        magnitudes = abs(indata)
        indata = signs | magnitudes

        #
        coeffs = pywt.wavedec(indata[:,1], wavelet=wavelet, mode=padding, level=level)
        coeffs_, slices = pywt.coeffs_to_array(coeffs)
        coeffs_ = np.multiply(coeffs_, factor)
        self.buffer_temp[:,1] = coeffs_.astype(np.int32)
        #
        coeffs = pywt.wavedec(indata[:,0], wavelet=wavelet, mode=padding, level=level)
        coeffs_, slices = pywt.coeffs_to_array(coeffs)
        coeffs_ = np.multiply(coeffs_, factor)
        self.buffer_temp[:,0] = coeffs_.astype(np.int32)

        self.NOBPTS = int(0.75*self.NOBPTS + 0.25*self.NORB)
        self.NOBPTS += self.skipped_bitplanes[(self.played_chunk_number+1) % self.cells_in_buffer]
        self.skipped_bitplanes[(self.played_chunk_number+1) % self.cells_in_buffer] = 0
        self.NOBPTS += 1
        if self.NOBPTS > self.max_NOBPTS:
            self.NOBPTS = self.max_NOBPTS

        #
        last_BPTS = - 1

        for bitplane_number in range(self.max_NOBPTS-1, last_BPTS, -1):
            self.send_bitplane(self.buffer_temp, bitplane_number)
        self.recorded_chunk_number = (self.recorded_chunk_number + 1) % self.MAX_CHUNK_NUMBER

    def record_send_and_play_stereo(self, indata, outdata, frames, time, status):
        indata[:,0] -= indata[:,1]
        self.send(indata)
        #
        chunk = self.buffer_coefs[self.played_chunk_number % self.cells_in_buffer]
        #
        self.buffer_coefs[self.played_chunk_number % self.cells_in_buffer] = np.zeros((self.frames_per_chunk, 2), dtype=np.int32)
        #
        chunk = np.divide(chunk, factor)

        #
        coeffs_from_arr = pywt.array_to_coeffs(chunk[:,1], self.coeff_slices, output_format="wavedec")
        sample = pywt.waverec(coeffs_from_arr, wavelet=wavelet, mode=padding)
        chunk[:,1] = sample
        #
        coeffs_from_arr = pywt.array_to_coeffs(chunk[:,0], self.coeff_slices, output_format="wavedec")
        sample = pywt.waverec(coeffs_from_arr, wavelet=wavelet, mode=padding)
        chunk[:,0] = sample

        #
        chunk = chunk.astype(np.int16)

        signs = chunk >> 15
        magnitudes = chunk & 0x7FFF
        #chunk = ((~signs & magnitudes) | ((-magnitudes) & signs))
        chunk = magnitudes + magnitudes*signs*2
        self._buffer[self.played_chunk_number % self.cells_in_buffer]  = chunk

        self._buffer[self.played_chunk_number % self.cells_in_buffer][:,0] += self._buffer[self.played_chunk_number % self.cells_in_buffer][:,1]
        self.play(outdata)

        self.received_bitplanes_per_chunk [self.played_chunk_number % self.cells_in_buffer] = 0
        #print(*self.received_bitplanes_per_chunk)

if __name__ == "__main__":
    intercom = Intercom_DWT()
    parser = intercom.add_args()
    args = parser.parse_args()
    intercom.init(args)
    intercom.run()
