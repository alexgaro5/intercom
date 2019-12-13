# Implementing a Data-Flow Control algorithm.

    #EXPLICATION:
    #
    #We have three new variables:
    #
    #	-number_of_bitplanes, it has a default value of sixteen times number_of_channels, and this is the number of bitplanes that we are going to send.
    #	-current_chunk_number, it's the current number of chunk.
    #	-bitplanes_recieved, it's the number of bitplanes that we recieved in the recieve method.
    #
    #We rewrite fourth method.
    #
    #	The first and the second method are the same, one of them is used when the number of channels is one, and the other when the number of channel is two.
    #First we convert two's complement to sign-magnitude number splitting the first column of the indata (sign) and calculating the absolute value to the rest colums of the indata (magnitude) and linking them again. 
    #Later, we change the number of bitplanes that we send. Before we send the same number for each chunk. Now we send a different number that we control with number_of_bitplane variable.
    #If the network is overloaded, the number of bitplanes decrease because the variable is updated in the recieved method.
    #
    #	The third is recieve method. We increase the bitplane_received varaible while the chunk number that we recieved is the same.
    #If the chunk_number  is not the same than current_chunk_numer, we check the number of bitplanes received, if this is less than number_of_bitplanes, we update the number of bitplanes that the computer send, doing a  weighted average between the number_of_bitplanes and the bitplanes received, to avoid overloading the network.
    #Also we update the current_chunk_number and reset the bitplane_received, because we have changed the chunk_number.
    #If the network works fine again, we have to increase the number_of_bitplane variable to send more bitplanes again, so we are going to try to increase this varaible for each chunk, so we wil get the maximum bitplanes that we can send if the network allow it.
    #
    #	The fourth method we convert two's complement to sign-madnitude to play the audio correctly. We use an algorithm that teacher shared with us.

import sounddevice as sd
import numpy as np
import struct
from intercom import Intercom
from intercom_binaural import Intercom_binaural

if __debug__:
    import sys

class Intercom_dfc(Intercom_binaural):

    def init(self, args):
        Intercom_binaural.init(self, args)
        self.send_packet_format = f"!HB{self.frames_per_chunk//8}B"

        #Current number of bitplanes sent.
        self.number_of_bitplanes = 16*self.number_of_channels
        #Current chunk number.
        self.current_chunk_number = 0
        #Number of bitplanes received in one chunk.
        self.bitplane_received = 0

    def record_send_and_play(self, indata, outdata, frames, time, status): 

        #We get the most significative column from indata (the first one, which has the numbers sign)
        sign = indata & 0x8000
        #We calculate the absolute value of the indata and we save it in magnitude.
        magnitude = abs(indata)
        #We add to magnitude the first column with the number sign, and we get the sign-magnitude representation, and we save it in indata.
        indata = sign | magnitude
        
        #The number of bitplanes that we are going to send will depend on the received biplanes. That is why the loop depends on a var.
        for bitplane_number in range(self.number_of_bitplanes-1, -1, -1):
            bitplane = (indata[:, bitplane_number%self.number_of_channels] >> bitplane_number//self.number_of_channels) & 1
            bitplane = bitplane.astype(np.uint8)
            bitplane = np.packbits(bitplane)
            message = struct.pack(self.packet_format, self.recorded_chunk_number, bitplane_number, *bitplane)
            self.sending_sock.sendto(message, (self.destination_IP_addr, self.destination_port))
        self.recorded_chunk_number = (self.recorded_chunk_number + 1) % self.MAX_CHUNK_NUMBER
        
        #In order to reset the default bitplanes number, for each chunk we will try to increase by one the number of bitplanes to send.
        if self.number_of_bitplanes < 16*self.number_of_channels: self.number_of_bitplanes += 1

        self.play(outdata)

    def record_send_and_play_stereo(self, indata, outdata, frames, time, status):

        #We get the most significative column from indata (the first one, which has the numbers sign)
        sign = indata & 0x8000
        #We calculate the absolute value of the indata and we save it in magnitude.
        magnitude = abs(indata)
        #We add to magnitude the first column with the number sign, and we get the sign-magnitude representation, and we save it in indata.
        indata = sign | magnitude

        indata[:,0] -= indata[:,1]   
        
        #The number of biplanes that we are going to send will depend on the received bitplanes. That is why the loop depends on a var.
        for bitplane_number in range((self.number_of_channels*16)-1, (self.number_of_channels*16)-1-self.number_of_bitplanes, -1):
            bitplane = (indata[:, bitplane_number%self.number_of_channels] >> bitplane_number//self.number_of_channels) & 1
            bitplane = bitplane.astype(np.uint8)
            bitplane = np.packbits(bitplane)
            message = struct.pack(self.packet_format, self.recorded_chunk_number, bitplane_number, *bitplane)
            self.sending_sock.sendto(message, (self.destination_IP_addr, self.destination_port))
        self.recorded_chunk_number = (self.recorded_chunk_number + 1) % self.MAX_CHUNK_NUMBER  

        self._buffer[self.played_chunk_number % self.cells_in_buffer][:,0] += self._buffer[self.played_chunk_number % self.cells_in_buffer][:,1]   
        
        #In order to reset the default bitplanes number, for each chunk we will try to increase by one the number of bitplanes to send.
        if self.number_of_bitplanes < 16*self.number_of_channels: self.number_of_bitplanes += 1

        self.play(outdata)

    def receive_and_buffer(self):
        message, source_address = self.receiving_sock.recvfrom(Intercom.MAX_MESSAGE_SIZE)
        chunk_number, bitplane_number, *bitplane = struct.unpack(self.packet_format, message)

        #We increase the bitplane counter, as we have received one.
        self.bitplane_received += 1
        #If there is a change of chunk...
        if self.current_chunk_number != chunk_number:
            #If we have received less bitplanes in the current chunk than in the previous chunk, we update the number of bitplanes that must be sent in the next chunk computing a weighted average with the received and sent bitplanes.
            if self.bitplane_received < self.number_of_bitplanes:
               self.number_of_bitplanes = int((self.number_of_bitplanes*0.8) + (self.bitplane_received*0.2))
            #We update the current chunk number.
            self.current_chunk_number = chunk_number
            #We reset the biplane var as we have changed to a different chunk.
            self.bitplane_received = 0

        bitplane = np.asarray(bitplane, dtype=np.uint8)
        bitplane = np.unpackbits(bitplane)
        bitplane = bitplane.astype(np.int16)
        self._buffer[chunk_number % self.cells_in_buffer][:, bitplane_number%self.number_of_channels] |= (bitplane << bitplane_number//self.number_of_channels)
        return chunk_number

    def play(self, outdata):
        chunk = self._buffer[self.played_chunk_number % self.cells_in_buffer]
        self._buffer[self.played_chunk_number % self.cells_in_buffer] = self.generate_zero_chunk()
        self.played_chunk_number = (self.played_chunk_number + 1) % self.cells_in_buffer

        #We get the most significative column from the chunk (the first one, which has the numbers sign)
        sign = chunk >> 15
        #We get the rest of the chunk.
        magnitude = chunk & 0x7FFF
        #If the number is positive, we dont change nothing, but if it is negative, we change it from sign-magnitude to two complement.
        outdata[:] = (~sign & magnitude) | (((magnitude & 0x8000) - magnitude) & sign) 

        if __debug__:
            sys.stderr.write("."); sys.stderr.flush()   


if __name__ == "__main__":
    intercom = Intercom_dfc()
    parser = intercom.add_args()
    args = parser.parse_args()
    intercom.init(args)
    intercom.run()