# Exploiting binaural redundancy.

import sounddevice as sd
import numpy as np
import struct
from intercom import Intercom
from intercom_bitplanes import Intercom_bitplanes

if __debug__:
    import sys

class Intercom_binaural(Intercom_bitplanes):

    def init(self, args):
        Intercom_bitplanes.init(self, args)
        if self.number_of_channels == 2:                                                              #If it is stereo, we run the new method defined below, if not, we use the previous record_send_and_play method.
            self.record_send_and_play = self.record_send_and_play_stereo

    def record_send_and_play_stereo(self, indata, outdata, frames, time, status):

        indata[:,0] -= indata[:,1]                                                                    #We substract the channel 0 to the channel 1 to make it lighter and we send it in bitplanes.
        self.record_and_send(indata)                                                                  #We call the method called 'send' to send el bitplanes.
        self._buffer[self.played_chunk_number % self.cells_in_buffer][:,0] += self._buffer[self.played_chunk_number % self.cells_in_buffer][:,1]    #When we have received all the bitplanes, we add the channel 0 to the channel 1 to restore and play it.
        self.play(outdata)

        if __debug__:
            sys.stderr.write("."); sys.stderr.flush()

if __name__ == "__main__":
    intercom = Intercom_binaural()
    parser = intercom.add_args()
    args = parser.parse_args()
    intercom.init(args)
    intercom.run()