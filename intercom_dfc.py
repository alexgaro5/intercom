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
        #El numero actual de bitplanes que se envian.
        self.number_of_bitplanes = 16*self.number_of_channels
        #El numero actual de chunk.
        self.current_chunk_number = 0
        #El numero de bitplanes recibidos en un chunk.
        self.bitplane_recieved = 0

    def receive_and_buffer(self):
        message, source_address = self.receiving_sock.recvfrom(Intercom.MAX_MESSAGE_SIZE)
        chunk_number, bitplane_number, *bitplane = struct.unpack(self.packet_format, message)

        #Incrementamos el contador de bitplane, pues hemos recibido uno.
        self.bitplane_recieved += 1
        #Si hay un cambio de chunk...
        if self.current_chunk_number != chunk_number:
            #Si se han recibido menos bitplanes en este chunk que en el anterior, se actualiza el numero de bitplanes a enviar para el siguiente chunk haciendo una media ponderada entre los bitplanes enviados y recibidos.
            if self.bitplane_recieved < self.number_of_bitplanes:
               self.number_of_bitplanes = (int)(self.number_of_bitplanes*0,8) + (self.bitplane_recieved*0,2)
            #actualizamos el numero de chunk actual,
            self.current_chunk_number = chunk_number
            #Reseteamos la variable de bitplanes a 0, pues hemos pasado de un chunk a otro diferente.
            self.bitplane_recieved = 0

        bitplane = np.asarray(bitplane, dtype=np.uint8)
        bitplane = np.unpackbits(bitplane)
        bitplane = bitplane.astype(np.int16)
        self._buffer[chunk_number % self.cells_in_buffer][:, bitplane_number%self.number_of_channels] |= (bitplane << bitplane_number//self.number_of_channels)
        return chunk_number

    def record_send_and_play(self, indata, outdata, frames, time, status): 
        
        #El numero de bitplanes que enviemos, dependerá de los bitplanes que se reciban, por eso el bucle depende de una variable.
        for bitplane_number in range(self.number_of_bitplanes-1, -1, -1):
            bitplane = (indata[:, bitplane_number%self.number_of_channels] >> bitplane_number//self.number_of_channels) & 1
            bitplane = bitplane.astype(np.uint8)
            bitplane = np.packbits(bitplane)
            message = struct.pack(self.packet_format, self.recorded_chunk_number, bitplane_number, *bitplane)
            self.sending_sock.sendto(message, (self.destination_IP_addr, self.destination_port))
        self.recorded_chunk_number = (self.recorded_chunk_number + 1) % self.MAX_CHUNK_NUMBER
        
        #Para intentar restablecer el numero por defecto de bitplanes, por cada chunk se intentará incrementar a uno más el numero de bitplanes a enviar. 
        if self.number_of_bitplanes < 16*self.number_of_channels: self.number_of_bitplanes += 1

        self.play(outdata)

    def record_send_and_play_stereo(self, indata, outdata, frames, time, status):

        indata[:,0] -= indata[:,1]   
        
        #El numero de bitplanes que enviemos, dependerá de los bitplanes que se reciban, por eso el bucle depende de una variable.
        for bitplane_number in range(self.number_of_bitplanes-1, -1, -1):
            bitplane = (indata[:, bitplane_number%self.number_of_channels] >> bitplane_number//self.number_of_channels) & 1
            bitplane = bitplane.astype(np.uint8)
            bitplane = np.packbits(bitplane)
            message = struct.pack(self.packet_format, self.recorded_chunk_number, bitplane_number, *bitplane)
            self.sending_sock.sendto(message, (self.destination_IP_addr, self.destination_port))
        self.recorded_chunk_number = (self.recorded_chunk_number + 1) % self.MAX_CHUNK_NUMBER     
        self._buffer[self.played_chunk_number % self.cells_in_buffer][:,0] += self._buffer[self.played_chunk_number % self.cells_in_buffer][:,1]   
        
        #Para intentar restablecer el numero por defecto de bitplanes, por cada chunk se intentará incrementar a uno más el numero de bitplanes a enviar. 
        if self.number_of_bitplanes < 16*self.number_of_channels: self.number_of_bitplanes += 1

        self.play(outdata)

if __name__ == "__main__":
    intercom = Intercom_dfc()
    parser = intercom.add_args()
    args = parser.parse_args()
    intercom.init(args)
    intercom.run()