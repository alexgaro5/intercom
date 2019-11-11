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

        indata[:,1] -= indata[:,0]                                                                    #We substract the channel 0 to the channel 1 to make it lighter and we send it in bitplanes.

        Intercom_bitplanes.send(self, indata)                                                         #We call the method called 'send' to send el bitplanes.

        self.recorded_chunk_number = (self.recorded_chunk_number + 1) % self.MAX_CHUNK_NUMBER
        chunk = self._buffer[self.played_chunk_number % self.cells_in_buffer]
        chunk[:,1] += chunk[:,0]                                                                      #When we have received all the bitplanes, we add the channel 0 to the channel 1 to restore and play it.
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