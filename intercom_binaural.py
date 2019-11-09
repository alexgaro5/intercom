# Exploiting binaural redundancy.

import sounddevice as sd
import numpy as np
import struct
from intercom import Intercom
from intercom_buffer import Intercom_buffer
from intercom_bitplanes import Intercom_bitplanes

if __debug__:
    import sys

class Intercom_binaural(Intercom_bitplanes):

    def init(self, args):
        Intercom_bitplanes.init(self, args)
        if self.number_of_channels == 2:                                                              #If it is stereo, we run the new method defined below, if not, we use the previous record_send_and_play method.
            self.record_send_and_play = self.record_send_and_play_stereo

    def record_send_and_play_stereo(self, indata, outdata, frames, time, status):

        indata[:,0] -= indata[:,1]                                                                    #We substract the channel 1 to the channel 0 to make it lighter and we send it in bitplanes.

        for bitplane_number in range(self.number_of_channels*16-1, -1, -1):
            bitplane = (indata[:, bitplane_number%self.number_of_channels] >> bitplane_number//self.number_of_channels) & 1
            bitplane = bitplane.astype(np.uint8)
            bitplane = np.packbits(bitplane)
            message = struct.pack(self.packet_format, self.recorded_chunk_number, bitplane_number, *bitplane)
            self.sending_sock.sendto(message, (self.destination_IP_addr, self.destination_port))

        self.recorded_chunk_number = (self.recorded_chunk_number + 1) % self.MAX_CHUNK_NUMBER
        chunk = self._buffer[self.played_chunk_number % self.cells_in_buffer]
        chunk[:,0] += chunk[:,1]                                                                      #When we have received all the bitplanes, we add the channel 1 to the channel 0 to restore and play it.
        self._buffer[self.played_chunk_number % self.cells_in_buffer] = self.generate_zero_chunk()
        self.played_chunk_number = (self.played_chunk_number + 1) % self.cells_in_buffer
        outdata[:] = chunk

        if __debug__:
            sys.stderr.write("."); sys.stderr.flush()

if __name__ == "__main__":
    intercom = Intercom_binaural()
    parser = intercom.add_args()
    args = parser.parse_args()
    intercom.init(args)
    intercom.run()