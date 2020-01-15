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

if __debug__:
    import sys

class Intercom_DWT(Intercom_empty):

    def init(self, args):
        Intercom_empty.init(self, args)

        zeros = np.zeros(self.samples_per_chunk)
        self.coeffs = pywt.wavedec(zeros, wavelet="db1", mode="per")
        _, self.coeff_slices = pywt.coeffs_to_array(self.coeffs)

    def send_bitplane(self, indata, bitplane_number):
            #print(indata.shape)
            bitplane = (indata[:, bitplane_number%self.number_of_channels] >> bitplane_number//self.number_of_channels) & 1
            bitplane = bitplane.astype(np.uint8)
            bitplane = np.packbits(bitplane)

            if(bitplane.sum() != 0):
                message = struct.pack(self.packet_format, self.recorded_chunk_number, bitplane_number, self.received_bitplanes_per_chunk[(self.played_chunk_number+1) % self.cells_in_buffer]+1, *bitplane)
                self.sending_sock.sendto(message, (self.destination_IP_addr, self.destination_port))
                return 0
            else:
                return 1

    def send(self, indata):

        coeffs = pywt.wavedec(indata[:,1], wavelet="db1", mode='per')
        coeffs_, slices = pywt.coeffs_to_array(coeffs)
        indata[:,1] = coeffs_.astype(np.int16)

        signs = indata & 0x8000
        magnitudes = abs(indata)
        indata = signs | magnitudes
        
        #We calculate the average congestion
        self.NOBPTS = int(0.75*self.NOBPTS + 0.25*self.NORB)
        #increase by one the number of bitplane to send the maximum if we dont have congestion.
        self.NOBPTS += 1

        #If number of bitplanes to send is greater than the maximum or the number of empty bitplane for each chunk is grater than 8, we skip the congestion calculation for the current chunk.
        if (self.NOBPTS > self.max_NOBPTS) or (int(self.previous_empty//self.number_of_channels) > 8):
            self.NOBPTS = self.max_NOBPTS

        #We save the number of empty bitplane to use it in the next chunk.
        self.previous_empty = self.empty
        #We reset the variable.
        self.empty = 0
        #We calculaet the last bitplane to send index.
        last_BPTS = self.max_NOBPTS - self.NOBPTS - 1
        
        #We increase the empty counter if the bitplane is empty.
        self.empty += self.send_bitplane(indata, self.max_NOBPTS-1)
        self.empty += self.send_bitplane(indata, self.max_NOBPTS-2)
        for bitplane_number in range(self.max_NOBPTS-3, last_BPTS, -1):
            self.empty += self.send_bitplane(indata, bitplane_number)
        self.recorded_chunk_number = (self.recorded_chunk_number + 1) % self.MAX_CHUNK_NUMBER

    def record_send_and_play_stereo(self, indata, outdata, frames, time, status):
        indata[:,0] -= indata[:,1]
        self.send(indata)
        chunk = self._buffer[self.played_chunk_number % self.cells_in_buffer]



        signs = chunk >> 15
        magnitudes = chunk & 0x7FFF
        #chunk = ((~signs & magnitudes) | ((-magnitudes) & signs))
        chunk = magnitudes + magnitudes*signs*2
        self._buffer[self.played_chunk_number % self.cells_in_buffer]  = chunk

        coeffs_from_arr = pywt.array_to_coeffs(chunk[:,1], self.coeff_slices, output_format="wavedec")

        print(len(chunk[:,1]))
        print(len(self.coeff_slices))
        
        sample = pywt.waverec(coeffs_from_arr, wavelet="db1", mode="per")
        #sample = pywt.waverec(self.coeffs, wavelet="db1", mode="per")
        chunk[:,1] = sample.astype(float)

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
