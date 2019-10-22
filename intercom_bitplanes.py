import sounddevice as sd
import numpy as np
import struct
from intercom_buffer import Intercom_buffer
from intercom import Intercom

if __debug__:
    import sys

class Intercom_bitplanes(Intercom_buffer):

    def init(self, args):
        Intercom_buffer.init(self, args)
        self.packet_format = f"HHH{self.frames_per_chunk}h"

    def run(self):
        self.recorded_chunk_number = 0
        self.played_chunk_number = 0

        def receive_and_buffer():

            for i in range(15,-1,-1):
                for j in range (0, self.number_of_channels):
                    package, source_address = self.receiving_sock.recvfrom(Intercom.MAX_MESSAGE_SIZE)
                    chunk_number, significant, channel, *bitplane = struct.unpack(self.packet_format, package)
                    bitplane = np.asarray(bitplane)
                    self._buffer[chunk_number % self.cells_in_buffer][:,channel] |= (bitplane << significant)
                      
            return chunk_number

        def record_send_and_play(indata, outdata, frames, time, status):

            for i in range(15,-1,-1):
                array = (indata & (1 << i)) >> i

                for j in range (0, self.number_of_channels):
                    message = struct.pack(self.packet_format, self.recorded_chunk_number, i, j, *array[:,j])
                    self.sending_sock.sendto(message, (self.destination_IP_addr, self.destination_port))

            self.recorded_chunk_number = (self.recorded_chunk_number + 1) % self.MAX_CHUNK_NUMBER
            chunk = self._buffer[self.played_chunk_number % self.cells_in_buffer]
            self._buffer[self.played_chunk_number % self.cells_in_buffer] = self.generate_zero_chunk()
            self.played_chunk_number = (self.played_chunk_number + 1) % self.cells_in_buffer

            outdata[:] = chunk

            if __debug__:
                sys.stderr.write("."); sys.stderr.flush()

        with sd.Stream(samplerate=self.frames_per_second, 
                       blocksize=self.frames_per_chunk, 
                       dtype=np.int16, 
                       channels=self.number_of_channels, 
                       callback=record_send_and_play):
            print("-=- Press CTRL + c to quit -=-")
            first_received_chunk_number = receive_and_buffer()
            self.played_chunk_number = (first_received_chunk_number - self.chunks_to_buffer) % self.cells_in_buffer
            while True:
                receive_and_buffer()

if __name__ == "__main__":
    intercom = Intercom_bitplanes()
    parser = intercom.add_args()
    args = parser.parse_args()
    intercom.init(args)
    intercom.run()