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
        self.packet_format = f"!HBB{self.frames_per_chunk//8}B"     #Formado Recorded_chunk, significativo, channel y bitplane

    def receive_and_buffer(self):
        
        package, source_address = self.receiving_sock.recvfrom(Intercom.MAX_MESSAGE_SIZE)               #Recibimos el paquete.
        chunk_number, significant, channel, *bitplane = struct.unpack(self.packet_format, package)      #Desempaquetamos el paquete.
        bitplane_int8 = np.asarray(bitplane, dtype = np.uint8)                                          #Pasamos el bitplane a int8.
        bitplaneunpackbits = np.unpackbits(bitplane_int8)                                               #Descompactamos el bitplane.
        bitplane_int16 = bitplaneunpackbits.astype(np.int16)                                            #Lo pasamos a int16.
        self._buffer[chunk_number % self.cells_in_buffer][:,channel] |= (bitplane_int16 << significant) #Guardamanos el bitplane en la posición del buffer y de channel necesario. En la posición significativa necesaria.
                      
        return chunk_number

    def record_send_and_play(self, indata, outdata, frames, time, status):
        #Recorremos el indata y vamos cogiendo columnas de mas a menos significativo.
        for significant in range(15,-1,-1):
            for channel in range (0, self.number_of_channels):      #De las columnas, cogemos un canal.
                array = (indata & (1 << significant)) >> significant        #Cogemos la columna.        
                array_channel = array[:,channel]                            #Cogemos el canal.            
                channel_int8 = array_channel.astype(np.uint8)               #Lo pasamos a int8.               
                channelpackbits = np.packbits(channel_int8)                 #Lo compactamos
                message = struct.pack(self.packet_format, self.recorded_chunk_number, significant, channel, *channelpackbits)       #Lo empaquetamos en el formado especificado anteriormente.
                self.sending_sock.sendto(message, (self.destination_IP_addr, self.destination_port))        #Enviamos el paquete.

        self.recorded_chunk_number = (self.recorded_chunk_number + 1) % self.MAX_CHUNK_NUMBER
        chunk = self._buffer[self.played_chunk_number % self.cells_in_buffer]
        self._buffer[self.played_chunk_number % self.cells_in_buffer] = self.generate_zero_chunk()
        self.played_chunk_number = (self.played_chunk_number + 1) % self.cells_in_buffer

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