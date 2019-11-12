# Implementing a Data-Flow Control algorithm.

import sounddevice as sd
import numpy as np
import struct
from intercom import Intercom
from intercom_binaural import Intercom_binaural

class Intercom_dfc(Intercom_binaural):

    def init(self, args):
        Intercom_binaural.init(self, args)
        self.send_packet_format = f"!HB{self.frames_per_chunk//8}B"
        self.number_of_packets = 16*self.number_of_channels
        self.current_chunk_number = 0
        self.count = 0

    def receive_and_buffer(self):
        message, source_address = self.receiving_sock.recvfrom(Intercom.MAX_MESSAGE_SIZE)
        chunk_number, bitplane_number, *bitplane = struct.unpack(self.packet_format, message)

        #NEW
        self.count += 1
        
        if (self.current_chunk_number != chunk_number) & (self.count < self.number_of_packets): 
            self.number_of_packets = self.count

        if self.current_chunk_number != chunk_number:
            self.current_chunk_number = chunk_number
            self.count = 0
        #NEW

        bitplane = np.asarray(bitplane, dtype=np.uint8)
        bitplane = np.unpackbits(bitplane)
        bitplane = bitplane.astype(np.int16)
        self._buffer[chunk_number % self.cells_in_buffer][:, bitplane_number%self.number_of_channels] |= (bitplane << bitplane_number//self.number_of_channels)
        return chunk_number

    def record_send_and_play(self, indata, outdata, frames, time, status): 
        
        #NEW
        for bitplane_number in range(self.number_of_packets-1, -1, -1):
            bitplane = (indata[:, bitplane_number%self.number_of_channels] >> bitplane_number//self.number_of_channels) & 1
            bitplane = bitplane.astype(np.uint8)
            bitplane = np.packbits(bitplane)
            message = struct.pack(self.packet_format, self.recorded_chunk_number, bitplane_number, *bitplane)
            self.sending_sock.sendto(message, (self.destination_IP_addr, self.destination_port))
        self.recorded_chunk_number = (self.recorded_chunk_number + 1) % self.MAX_CHUNK_NUMBER
        
        if self.number_of_packets < 16*self.number_of_channels: self.number_of_packets += 1
        #NEW

        self.play(outdata)

    def record_send_and_play_stereo(self, indata, outdata, frames, time, status):

        indata[:,0] -= indata[:,1]   
        
        #NEW
        for bitplane_number in range(self.number_of_packets-1, -1, -1):
            bitplane = (indata[:, bitplane_number%self.number_of_channels] >> bitplane_number//self.number_of_channels) & 1
            bitplane = bitplane.astype(np.uint8)
            bitplane = np.packbits(bitplane)
            message = struct.pack(self.packet_format, self.recorded_chunk_number, bitplane_number, *bitplane)
            self.sending_sock.sendto(message, (self.destination_IP_addr, self.destination_port))
        self.recorded_chunk_number = (self.recorded_chunk_number + 1) % self.MAX_CHUNK_NUMBER     
        self._buffer[self.played_chunk_number % self.cells_in_buffer][:,0] += self._buffer[self.played_chunk_number % self.cells_in_buffer][:,1]   
        
        if self.number_of_packets < 16*self.number_of_channels: self.number_of_packets += 1
        #NEW

        self.play(outdata)

if __name__ == "__main__":
    intercom = Intercom_dfc()
    parser = intercom.add_args()
    args = parser.parse_args()
    intercom.init(args)
    intercom.run()