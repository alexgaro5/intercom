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
        self.packet_format = f"!HBB{self.frames_per_chunk//8}B"     #Format Recorded_chunk, significativo, channel y bitplane. The /8 is to compact the package from int16 to int8, so
																	#the packet size is smaller 

    def receive_and_buffer(self):
                
        package, source_address = self.receiving_sock.recvfrom(Intercom.MAX_MESSAGE_SIZE)                   #Receive the package     
        chunk_number, significant, channel, *bitplane = struct.unpack(self.packet_format, package)          #Unpack the package      
        bitplane_int8 = np.asarray(bitplane, dtype = np.uint8)                                              #Change the bitplane to int8.      
        bitplaneunpackbits = np.unpackbits(bitplane_int8)                                                   #Uncompact the bitplane.         
        bitplane_int16 = bitplaneunpackbits.astype(np.int16)                                                #Change the format of the bitplane to int16. 
        self._buffer[chunk_number % self.cells_in_buffer][:,channel] |= (bitplane_int16 << significant)     #Save the bitplane in the index of the buffer and channel, in the significative index.																											
                      
        return chunk_number

    def record_send_and_play(self, indata, outdata, frames, time, status):
																																	
        for significant in range(15,-1,-1):                                                                                         #Go through in indata and get the column in decreasing significative order
            array = (indata & (1 << significant)) >> significant                                                                    #Get the significative column 
            for channel in range (0, self.number_of_channels):                                                                      #In the selected column, go through the channels one by one.
                array_channel = array[:,channel]                                                                                    #Get the selected channel. 
                channel_int8 = array_channel.astype(np.uint8)                                                                       #Change the format to int8. 
                channelpackbits = np.packbits(channel_int8)                                                                         #Compact the information.
                message = struct.pack(self.packet_format, self.recorded_chunk_number, significant, channel, *channelpackbits)       #Pack the information with the specified format.
                self.sending_sock.sendto(message, (self.destination_IP_addr, self.destination_port))                                #Send the package.           

        
        self.recorded_chunk_number = (self.recorded_chunk_number + 1) % self.MAX_CHUNK_NUMBER               #Increase the record_chunk_number.
        chunk = self._buffer[self.played_chunk_number % self.cells_in_buffer]                               #Get one package from the buffer to read the information.
        self._buffer[self.played_chunk_number % self.cells_in_buffer] = self.generate_zero_chunk()          #Change the value in the position to zero.
        self.played_chunk_number = (self.played_chunk_number + 1) % self.cells_in_buffer                    #Increase the played_chunk_number.

        outdata[:] = chunk
        if __debug__:
            sys.stderr.write("."); sys.stderr.flush()

    def run(self):
        self.recorded_chunk_number = 0
        self.played_chunk_number = 0

        with sd.Stream(samplerate=self.frames_per_second, 
                    blocksize=self.frames_per_chunk, 
                    dtype=np.int16, 
                    channels=self.number_of_channels, 
                    callback=self.record_send_and_play):
            print("-=- Press CTRL + c to quit -=-")
            first_received_chunk_number = self.receive_and_buffer()
            self.played_chunk_number = (first_received_chunk_number - self.chunks_to_buffer) % self.cells_in_buffer
            while True:
                self.receive_and_buffer()

if __name__ == "__main__":
    intercom = Intercom_bitplanes()
    parser = intercom.add_args()
    args = parser.parse_args()
    intercom.init(args)
    intercom.run()