# Implementing a Data-Flow Control algorithm.

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

        #Obtenemos la columna mas significativa del indata (la primera, que contiene el signo de los numeros).
        sign = indata & 0x8000
        #Ponemos en valor absoluto todo el indata y lo guardamos en magnitude.
        magnitude = abs(indata)
        #Añadimos a maginute la primera columna con el signo del número, obteniendo de esta manera el signo-magnutud, y lo guardamos en indata.
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

        #Obtenemos la columna mas significativa del indata (la primera, que contiene el signo de los numeros).
        sign = indata & 0x8000
        #Ponemos en valor absoluto todo el indata y lo guardamos en magnitude.
        magnitude = abs(indata)
        #Añadimos a maginute la primera columna con el signo del número, obteniendo de esta manera el signo-magnutud, y lo guardamos en indata.
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

	    #Obtenemos la columna mas significativa del chunk (la primera, que contiene el signo de los numeros).
        sign = chunk >> 15
        #Obtenemos el resto del chunk.
        magnitude = chunk & 0x7FFF
        #Si el numero es positivo, no se hace nada, si es negativo, se pasa a de signo magnitud a complemento A2.
        outdata[:] = (~sign & magnitude) | (((magnitude & 0x8000) - magnitude) & sign) 

        if __debug__:
            sys.stderr.write("."); sys.stderr.flush()   


if __name__ == "__main__":
    intercom = Intercom_dfc()
    parser = intercom.add_args()
    args = parser.parse_args()
    intercom.init(args)
    intercom.run()